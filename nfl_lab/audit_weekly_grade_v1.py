"""Bounded operational grading composition; no acquisition, fits or publication.

The parent authenticates restored captures, provider observations and fresh
grading readback through a LIVE callback. JSON flags are not that authority.
The unchanged resolver, complete-week gate, losses and P2 selector are reused.
An explicit prevalue game-to-capture assignment prevents repeated daily
captures becoming extra games. Old history stays a separate immutable anchor.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import codecs
import gzip
import hashlib
import io
from itertools import chain, zip_longest
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import time
import zlib

from . import audit_weekly_archive_v1 as archive, audit_weekly_epoch_v1 as epoch
from . import weekly_grading as grading, weekly_adaptive as selector
from . import gha_private_checkpoint as cp, private_draft_store as store, state
from . import audit_weekly_retained_v1 as retained, weekly_durable_acceptance as acceptance
from .operational_io import operational_io
from .operational_storage import StorageIntegrityError, StorageQuotaError, _digest_file, _no_symlinks
from .owned_reference_batch import validate_owned_references

VERSION = "audit-weekly-grade-v1"
LIMITS = dict(captures=36, forecast_rows=648000, opportunities=36000,
    observation_rows=36000, revisions=144000, games=576, encoded_bytes=8 << 20,
    decoded_bytes=64 << 20, row_bytes=32768, wall_seconds=180, CPU_seconds=120,
    RSS_bytes=512 << 20, threads=2, fits=0, searches=0, retries=0)
POPULATION_RULE = "EXACT_PREVALUE_GAME_CAPTURE_ASSIGNMENT_NO_REPEAT_WEIGHT"
_KEY = object()
SNAPSHOT_KEYS = {"schema_version","epoch_sha256","legacy_history_binding","captures","collector_records","versions",
    "finality_records","weeks","pending_weeks","week_revisions","known_versions","known_weeks","actual_completed_at",
    "new_revisions","local_only","metadata_remote_durability_qualified","successful_forecast","scientific_qualification","public_release","fits","searches","code_pins"}
RETAINED_KEYS = {"schema_version","state","created_at_utc","registration_sha256","current_root_go_sha256","current",
    "original_archive","original_reader_handoff","original_index","original_reader_witness","historical_producer_proof",
    "historical_reader_witness","historical_job_evidence","current_restore_proofs","original_exporter_proof_scope",
    "aliases","metadata","r0","previous_state","previous_state_aliases","original_physical_bindings","validation",
    "files_sha256","HTTP_calls","RSS_peak_bytes","fits","model_decodes","source_acquisitions","protected_outcome_reads",
    "remote_writes","model_replay_performed","public_export_authorized","public_release","successful_forecast"}


class GradeError(ValueError): pass


def require(value, code):
    if not value: raise GradeError(code)


def now(): return datetime.now(timezone.utc)


def _canonical_chunks(document):
    # Same JSON bytes as state.canonical, without its full string + UTF-8 copy.
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    def pieces(value):
        if isinstance(value, _PagedRows):
            yield b"["
            for i, page in enumerate(value._pages):
                if i: yield b","
                yield zlib.decompress(page)[1:-1]
            yield b"]"
        elif isinstance(value, dict):
            yield b"{"
            for i, (key, item) in enumerate(sorted(value.items())):
                if i: yield b","
                yield encoder.encode(key).encode("utf-8"); yield b":"
                yield from pieces(item)
            yield b"}"
        elif isinstance(value, (list, tuple)):
            yield b"["
            for i, item in enumerate(value):
                if i: yield b","
                yield from pieces(item)
            yield b"]"
        else:
            yield encoder.encode(value).encode("utf-8")
    pending = bytearray()
    for part in pieces(document):
        pending.extend(part)
        if len(pending) >= 32768:
            yield bytes(pending); pending.clear()
    if pending: yield bytes(pending)


def _digest(document):
    result = hashlib.sha256()
    for chunk in _canonical_chunks(document): result.update(chunk)
    return result.hexdigest()


def _equal_chunks(left, right):
    """Literal byte equality across different bounded chunk boundaries."""
    right = iter(right); pending = memoryview(b"")
    for chunk in left:
        chunk = memoryview(chunk)
        while chunk:
            if not pending:
                try: pending = memoryview(next(right))
                except StopIteration: return False
            count = min(len(chunk), len(pending))
            if chunk[:count] != pending[:count]: return False
            chunk, pending = chunk[count:], pending[count:]
    return not pending and next(right, b"") == b""


def _immutable(*args, **kwargs):
    raise TypeError("PAGED_ORIGINAL_ROWS_ARE_IMMUTABLE")


class _FrozenDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable
    def __deepcopy__(self, memo):
        return {k: deepcopy(v, memo) for k, v in self.items()}


class _FrozenList(list):
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _immutable
    def __deepcopy__(self, memo): return [deepcopy(v, memo) for v in self]


def _freeze(value, pool=None):
    if isinstance(value, _PagedRows): return value
    if isinstance(value, dict): return _FrozenDict((_freeze(k, pool), _freeze(v, pool)) for k, v in value.items())
    if isinstance(value, list): return _FrozenList(_freeze(v, pool) for v in value)
    # A bounded iterator-local pool shares repeated field names, identities and
    # provenance strings. Unique values beyond the pool stay intact.
    if type(value) is str and pool is not None and len(pool) < 16384 and len(value) <= 128:
        return pool.setdefault(value, value)
    return value


class _PagedRows(list):
    """Lossless immutable JSON rows; at most 64 rows decoded by an iterator.

    Pages are process-local bytes, not authority or a new persistence format.
    The public document still serializes to the exact original JSON arrays.
    Copies can share these immutable pages; edits fail immediately rather than
    silently changing a detached row. Ordinary document fields remain sealed by
    the full canonical digest. No source row or historical revision is evicted.
    """
    def __init__(self, rows=()):
        super().__init__()
        pages = []; count = 0; pending = []
        for row in rows:
            pending.append(row); count += 1
            if len(pending) == 64:
                pages.append(zlib.compress(state.canonical(pending), 1)); pending = []
        if pending: pages.append(zlib.compress(state.canonical(pending), 1))
        object.__setattr__(self, "_pages", tuple(pages)); object.__setattr__(self, "_count", count)
    @classmethod
    def join(cls, parts):
        result = cls()
        object.__setattr__(result, "_pages", tuple(page for part in parts for page in part._pages))
        object.__setattr__(result, "_count", sum(len(part) for part in parts))
        return result
    def __len__(self): return self._count
    def __iter__(self): return self.category_rows(None)
    def category_rows(self, category):
        pool = {}
        for page in self._pages:
            for row in cp.strict_json(zlib.decompress(page)):
                if category is None or row["category"] == category: yield _freeze(row, pool)
    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self[i] for i in range(start, stop, step)]
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        # A joined stream can have short pages at slot boundaries.
        for page in self._pages:
            rows = cp.strict_json(zlib.decompress(page))
            if index < len(rows): return _freeze(rows[index])
            index -= len(rows)
        raise IndexError(index)
    def __eq__(self, other):
        if not isinstance(other, (list, tuple)) or len(self) != len(other): return False
        if isinstance(other, _PagedRows) and self._pages == other._pages: return True
        if isinstance(other, _PagedRows) and _equal_chunks(_canonical_chunks(self), _canonical_chunks(other)): return True
        missing = object()
        return all(a == b for a, b in zip_longest(self, other, fillvalue=missing))
    def __ne__(self, other): return not self == other
    def __deepcopy__(self, memo): return self
    def __copy__(self): return self
    def copy(self): return self
    def __contains__(self, item): return any(row == item for row in self)
    def __reversed__(self): return (self[i] for i in range(len(self)-1, -1, -1))
    def __add__(self, other):
        if not isinstance(other, list): return NotImplemented
        return list(chain(self, other))
    def __radd__(self, other):
        if not isinstance(other, list): return NotImplemented
        return list(chain(other, self))
    def __mul__(self, count): return list(self) * count
    __rmul__ = __mul__
    def count(self, item): return sum(row == item for row in self)
    def index(self, item, start=0, stop=None):
        start, stop, _ = slice(start, stop).indices(len(self))
        for i, row in enumerate(self):
            if start <= i < stop and row == item: return i
        raise ValueError("row is not in paged originals")
    __setattr__ = __delattr__ = _immutable
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _immutable


class _JSONStream:
    """Strict incremental JSON, paging original rows without changing bytes."""
    def __init__(self, stream, cap, *, paged_keys=("forecasts", "selected", "opportunities", "rows", "collector_records")):
        self.stream, self.cap, self.total = stream, cap, 0
        self.buffer, self.pos, self.eof = "", 0, False
        self.text_decoder = None
        self.decoder = json.JSONDecoder(object_pairs_hook=self.pairs, parse_constant=self.bad_constant)
        self.paged_keys = paged_keys
        self.pool = {}
    @staticmethod
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_PRIVATE_JSON"); result[key] = value
        return result
    @staticmethod
    def bad_constant(_): raise store.StoreError("NONFINITE_PRIVATE_JSON")
    def fill(self):
        allowance = self.cap - self.total + 1
        raw = self.stream.read(min(32768, allowance))
        # json.loads(bytes) also accepts UTF BOMs and UTF-16/32. Retain that
        # behavior, including when a reader splits the encoding prefix.
        while self.text_decoder is None and 0 < len(raw) < min(4, allowance):
            extra = self.stream.read(min(4-len(raw), allowance-len(raw)))
            if not extra: break
            raw += extra
        if self.text_decoder is None:
            self.text_decoder = codecs.getincrementaldecoder(json.detect_encoding(raw))()
        self.total += len(raw)
        require(self.total <= self.cap, "FINITE_FULL_GRADING_SNAPSHOT")
        self.eof = not raw
        self.buffer = self.buffer[self.pos:] + self.text_decoder.decode(raw, final=self.eof); self.pos = 0
    def peek(self):
        while True:
            while self.pos < len(self.buffer) and self.buffer[self.pos] in " \t\r\n": self.pos += 1
            if self.pos < len(self.buffer): return self.buffer[self.pos]
            if self.eof: return ""
            self.fill()
    def take(self, char):
        require(self.peek() == char, "STRICT_GRADING_JSON")
        self.pos += 1
    def scalar(self):
        self.peek()
        while True:
            try: value, end = self.decoder.raw_decode(self.buffer, self.pos)
            except json.JSONDecodeError:
                if self.eof: raise
                self.fill(); continue
            if end == len(self.buffer) and not self.eof:
                self.fill(); continue
            if end < len(self.buffer) and self.buffer[end] not in " \t\r\n,:]}" and not self.eof:
                # raw_decode can accept just the integer prefix of a split
                # fractional/exponent token. Wait for its complete delimiter.
                self.fill(); continue
            require(end == len(self.buffer) or self.buffer[end] in " \t\r\n,:]}", "STRICT_GRADING_JSON")
            self.pos = end
            if type(value) is str and len(value) <= 128 and len(self.pool) < 16384:
                value = self.pool.setdefault(value, value)
            return value
    def value(self, key=None):
        char = self.peek()
        if char == "{":
            self.take("{"); result = {}
            if self.peek() != "}":
                while True:
                    require(self.peek() == '"', "STRICT_GRADING_JSON")
                    name = self.scalar()
                    require(name not in result, "DUPLICATE_PRIVATE_JSON")
                    self.take(":"); result[name] = self.value(name)
                    if self.peek() == "}": break
                    self.take(",")
            self.take("}"); return result
        if char == "[":
            self.take("[")
            def rows():
                if self.peek() != "]":
                    while True:
                        yield self.scalar() if key in self.paged_keys else self.value()
                        if self.peek() == "]": break
                        self.take(",")
                self.take("]")
            return _PagedRows(rows()) if key in self.paged_keys else list(rows())
        return self.scalar()
    def load(self):
        result = self.value()
        require(self.peek() == "" and self.eof, "STRICT_GRADING_JSON")
        return result


def _unpack(body, cap):
    # read(cap+1) reserves the whole 64 MiB even for a tiny gzip member.
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        return _JSONStream(stream, cap).load()


def _read_owned(storage, ref, cap=2 << 20, *, raw=False):
    # Preserve ownership/hash/size checks while reserving the actual file size.
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap, "EXACT_CHECKPOINT_REFERENCE")
    return archive.read_owned(storage, ref, ref["bytes"], raw=raw)


def pins():
    root = Path(__file__).resolve().parents[1]
    names = ("nfl_lab/audit_weekly_grade_v1.py", "tools/audit_weekly_grade_v1.py",
        "nfl_lab/weekly_grading.py", "nfl_lab/weekly_adaptive.py", "nfl_lab/state.py",
        "nfl_lab/audit_weekly_epoch_v1.py", "nfl_lab/weekly_generic_producer.py",
        "nfl_lab/audit_weekly_retained_v1.py", "nfl_lab/weekly_durable_acceptance.py")
    return {name: store.sha(store.read_local(root/name, 2 << 20)) for name in names}


def _authenticate(callback, kind, document, at):
    require(callable(callback), "EXTERNAL_LIVE_PARENT_AUTHENTICATOR_REQUIRED")
    request = dict(schema_version=VERSION+"-authentication-request", kind=kind,
        inputs_sha256=_digest(document), at=state.utc(at).isoformat())
    # The callback must bind this digest to its genuine root/source/API/body
    # evidence. Neither an execution_authorized JSON flag nor a saved return
    # value can replace the callback on a new process.
    require(callback(deepcopy(request)) is True, "EXTERNAL_PARENT_AUTHENTICATION_REJECTED")
    return request


class _Sealed:
    def __init__(self, document, key):
        require(key is _KEY, "LIVE_PARENT_BOUND_INPUT_REQUIRED")
        self.document = deepcopy(document); self.sha256 = _digest(document)
    def verify(self):
        require(self.sha256 == _digest(self.document), "SEALED_OPERATIONAL_INPUT_CHANGED")
    def __reduce__(self): raise GradeError("LIVE_INPUT_CANNOT_BE_SERIALIZED")


class Population(_Sealed): pass
class Capture(_Sealed): pass
class _ObservationRows(_PagedRows):
    # A caller may copy a bound batch to form its next observation request.
    # Preserve the original editable-list deepcopy contract for that boundary.
    def __deepcopy__(self, memo): return deepcopy(list(self), memo)


class Observations(_Sealed):
    def __init__(self, document, key):
        require(key is _KEY, "LIVE_PARENT_BOUND_INPUT_REQUIRED")
        self.document = {name: _ObservationRows(value) if name == "observations" else deepcopy(value)
            for name,value in document.items()}
        self.sha256 = _digest(document)
class Snapshot(_Sealed):
    def verify(self):
        super().verify()
        require(self._binding_sha256 == state.digest(self.binding), "SNAPSHOT_BYTE_BINDING_CHANGED")
class DurableHistory(_Sealed): pass


def population_template(registered, choice):
    """Parent registers this NEW assignment before values; no default ranking."""
    return dict(schema_version=VERSION+"-population", state="PREPARED_UNREGISTERED",
        epoch_sha256=registered.epoch.sha256, choice_sha256=choice.sha256,
        source_policy_sha256=cp.POLICY_SHA, stream_id=None, registered_at=None,
        horizon="player_game", population="REGISTERED_PRIMARY_ROLES",
        rule=POPULATION_RULE, assignments={g: None for g in choice.document["slate"]["game_cutoffs"]},
        role_catalog_sha256=None, code_pins=pins())


def bind_population(document, registered, choice, *, authenticate, at):
    require(type(registered) is epoch.RegisteredEpoch and type(choice) is epoch.EpochChoice,
        "TYPED_REGISTERED_EPOCH_AND_CHOICE_REQUIRED")
    choice.verify(registered, state.utc(at))
    expected = population_template(registered, choice)
    require(type(document) is dict and set(document) == set(expected)
        and document["state"] == "ROOT_REGISTERED" and document["code_pins"] == pins()
        and all(document[k] == expected[k] for k in ("schema_version", "epoch_sha256", "choice_sha256",
            "source_policy_sha256", "horizon", "population", "rule")), "EXPLICIT_REGISTERED_ISSUANCE_POPULATION_REQUIRED")
    require(type(document["stream_id"]) is str and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", document["stream_id"])
        and store.HASH.fullmatch(str(document["role_catalog_sha256"]))
        and set(document["assignments"]) == set(expected["assignments"])
        and all(store.HASH.fullmatch(str(v)) for v in document["assignments"].values())
        and state.utc(document["registered_at"]) <= state.utc(at), "PREVALUE_EXACT_CAPTURE_ASSIGNMENTS_REQUIRED")
    _authenticate(authenticate, "POPULATION_BEFORE_VALUES", document, at)
    return Population(document, _KEY)


def _rows(storage, ref, *, maximum, budget):
    encoded = _read_owned(storage, ref, LIMITS["encoded_bytes"], raw=True)
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as reader:
        def rows():
            count = 0
            while True:
                raw = reader.readline(LIMITS["row_bytes"]+1)
                if not raw: break
                budget[0] += len(raw); count += 1
                require(len(raw) <= LIMITS["row_bytes"] and raw.endswith(b"\n")
                    and count <= maximum and budget[0] <= LIMITS["decoded_bytes"], "FINITE_ORIGINAL_FORECAST_STREAM")
                yield cp.strict_json(raw)
        return _PagedRows(rows())


def _native_metadata(proof, identity, binding_sha256, at):
    require(type(proof) is dict and set(proof) == store.BASE_PROOF_FIELDS | store.PHASE_FIELDS['restore']
        and proof['schema_version'] == 'weekly-private-proof-v2.1' and proof['phase'] == 'restore'
        and proof['operation'] == store.PHASE_OPERATION['restore']
        and proof['binding_sha256'] == binding_sha256 and proof['config_sha256'] == store.config_sha()
        and acceptance.restored_identity(proof) == identity
        and proof['exact_readback'] is proof['separate_process'] is proof['draft_before_after'] is True
        and type(proof['HTTP_calls']) is int and 10 <= proof['HTTP_calls'] <= store.MAX_CALLS
        and type(proof['transfer_bytes']) is int and 0 < proof['transfer_bytes'] <= store.TRANSFER_CAP
        and type(proof['bytes']) is int and 0 < proof['bytes'] <= store.ASSET_CAP
        and store.HASH.fullmatch(str(proof['payload_sha256']))
        and state.utc(proof['started_at_utc']) <= state.utc(proof['created_at_utc']) <= state.utc(at),
        'EXACT_PARENT_AUTHENTICATED_NATIVE_METADATA_PROOF')


def _retained_evidence(restored, storage, at):
    """NEW retained contract, after LIVE parent authentication; no relabeling.

    Historical writer/reader evidence establishes original persistence. Current
    GETs authorize recovery only and never replace original pregame clocks.
    The parent revalidates actual API/source/root authority, not saved booleans.
    """
    require(set(restored) == RETAINED_KEYS and restored['state'] == 'PRIVATE_PRIOR_CAPTURE_RESTORED'
        and all(type(restored[k]) is int and restored[k] == 0 for k in ('fits','model_decodes','source_acquisitions','protected_outcome_reads','remote_writes'))
        and restored['model_replay_performed'] is restored['public_export_authorized'] is restored['public_release'] is restored['successful_forecast'] is False
        and restored['validation'].get('qualified_selected') is restored['validation'].get('replay_ready') is True
        and restored['original_exporter_proof_scope'] == 'COMPLETED_JOB_API_AND_PINNED_WORKFLOW_PERMISSIONS_NOT_RETAINED_RAW_EXPORT_PROOF'
        and all(store.HASH.fullmatch(str(restored[k])) for k in ('registration_sha256','current_root_go_sha256','files_sha256')),
        'CLOSED_AUTHENTICATED_RETAINED_CAPTURE_RESULT')
    handoff=restored['original_archive']; reader_handoff=restored['original_reader_handoff']
    archive.safe_handoff(handoff)
    require(set(reader_handoff) == {'schema_version','archive','restorer','witness_descriptor'}
        and reader_handoff['schema_version'] == archive.VERSION+'-reader-handoff' and reader_handoff['archive'] == handoff
        and handoff['archive_state'] == 'COMPLETE_CAPTURE' and restored['files_sha256'] == handoff['files_sha256'],
        'EXACT_ORIGINAL_RETAINED_CAPTURE_HANDOFF')
    raw=archive.read_owned(storage,restored['original_index'],archive.INDEX_CAP,raw=True)
    require(store.sha(raw) == handoff['index_descriptor']['entry']['payload']['sha256'], 'ORIGINAL_RETAINED_INDEX_BYTES')
    index=archive.check_index(archive.unpack(raw,archive.INDEX_PLAIN_CAP),handoff)
    raw_witness=archive.read_owned(storage,restored['original_reader_witness'],archive.WITNESS_CAP,raw=True)
    witness=archive.unpack(raw_witness,archive.WITNESS_CAP)
    entry=cp.descriptor_meta(reader_handoff['witness_descriptor'],archive.WITNESS_CAP)
    require(store.sha(raw_witness) == entry['payload']['sha256'] and witness == restored['historical_reader_witness']
        and set(witness) == retained.WITNESS_KEYS and witness['schema_version'] == archive.VERSION+'-witness'
        and witness['restorer'] == reader_handoff['restorer'] and witness['index_sha256'] == store.sha(raw)
        and witness['files_sha256'] == handoff['files_sha256'] and witness['validation'] == restored['validation']
        and witness['archive_state'] == 'COMPLETE_CAPTURE' and witness['public_export_authorized'] is witness['successful_forecast'] is False
        and witness['producer_proof_sha256'] == store.sha(store.canonical(index['producer_proof']))
        and index['producer_proof'] == restored['historical_producer_proof'], 'ORIGINAL_RETAINED_WITNESS_AND_PRODUCER')
    originals={f['logical_path']:f for f in index['files']}; aliases=restored['aliases']
    require(set(aliases) == set(originals) and all((aliases[n]['bytes'],aliases[n]['sha256']) == (f['bytes'],f['sha256']) for n,f in originals.items())
        and restored['original_physical_bindings'] == index['census']['physical_origins'], 'FULL_RETAINED_ALIAS_CENSUS')
    archive.validate_owned_references(storage,{ref['path']:ref['sha256'] for ref in aliases.values()})
    current=acceptance.identity(restored['current']); producer=acceptance.identity(handoff['producer']); reader=acceptance.identity(witness['restorer'])
    require(current['run_id'] != handoff['run_id']
        and reader['run_id'] == producer['run_id'] == handoff['run_id'] and reader['source_sha'] == producer['source_sha'] == handoff['source_sha']
        and reader['workflow_ref'] == producer['workflow_ref'] and reader['job_id'] == handoff['jobs']['restore']
        and len({current['process_identity'],producer['process_identity'],reader['process_identity']}) == 3
        and entry['writer_run_id'] == handoff['run_id'] and entry['producer_process'] == reader['process_identity'], 'DISTINCT_RETAINED_CURRENT_AND_HISTORICAL_IDENTITIES')
    jobs=restored['historical_job_evidence']
    require(set(jobs) == {'produce','restore','consume'} and len({j['api_job_id'] for j in jobs.values()}) == 3,
        'ALL_ORIGINAL_RETAINED_JOB_EVIDENCE')
    for role,j in jobs.items():
        require(j['repository'] == store.REPO and j['run_id'] == handoff['run_id'] and j['source_sha'] == handoff['source_sha']
            and j['workflow_ref'] == producer['workflow_ref'] and j['job_id'] == handoff['jobs'][role]
            and j['status'] == 'completed' and j['conclusion'] == 'success' and j['verified_permissions'] == dict(contents='write',actions='read')
            and state.utc(j['started_at']) <= state.utc(j['completed_at']) <= state.utc(restored['created_at_utc']) <= state.utc(at), 'ORIGINAL_RETAINED_SUCCESSFUL_JOB_CONTEXT')
    require(jobs['produce']['api_job_id'] == producer['api_job_id'] and jobs['restore']['api_job_id'] == reader['api_job_id']
        and current['api_job_id'] not in {j['api_job_id'] for j in jobs.values()}
        and state.utc(jobs['produce']['completed_at']) <= state.utc(jobs['restore']['started_at'])
        and state.utc(jobs['restore']['completed_at']) <= state.utc(jobs['consume']['started_at']), 'ORIGINAL_RETAINED_ORDERED_THREE_JOBS')
    binding_sha=store.sha(store.canonical(handoff['runtime_binding']))
    require(entry['binding_sha256'] == binding_sha, 'ORIGINAL_RETAINED_WITNESS_NAMESPACE')
    expected=[(len(raw),store.sha(raw))]+[(v['bytes'],v['sha256']) for v in index['groups']]
    require([(p['bytes'],p['payload_sha256']) for p in witness['proofs']] == expected, 'ALL_HISTORICAL_READER_PROOFS')
    for p in witness['proofs']:
        _native_metadata(p,reader,binding_sha,at)
        require(state.utc(jobs['restore']['started_at']) <= state.utc(p['started_at_utc']) <= state.utc(p['created_at_utc'])
            <= state.utc(witness['actual_completed_at']) <= state.utc(jobs['restore']['completed_at']), 'ORIGINAL_RETAINED_READER_CLOCKS')
    current_proofs=restored['current_restore_proofs']
    require(type(current_proofs) is list and [(p['bytes'],p['payload_sha256']) for p in current_proofs] ==
        [(len(raw),store.sha(raw)),(len(raw_witness),store.sha(raw_witness))]+expected[1:], 'ALL_CURRENT_RETAINED_RECOVERY_PROOFS')
    for p in current_proofs:
        _native_metadata(p,current,binding_sha,at)
        require(state.utc(jobs['consume']['completed_at']) < state.utc(p['started_at_utc']) <= state.utc(p['created_at_utc'])
            <= state.utc(restored['created_at_utc']), 'CURRENT_RECOVERY_CLOCKS_NEVER_BACKDATED')
    original_clocks=[jobs['produce']['completed_at'],jobs['restore']['completed_at'],witness['actual_completed_at']]
    original_clocks += [p['created_at_utc'] for p in witness['proofs']]
    return dict(known_by=max(original_clocks,key=state.utc),index_sha256=store.sha(raw),
        recovery_completed_at=restored['created_at_utc'],timeliness_scope='ORIGINAL_NATIVE_READER_AND_COMPLETED_WRITER_READER_JOBS',
        current_root_go_sha256=restored['current_root_go_sha256'],current_proofs_sha256=state.digest(current_proofs),
        original_reader_witness_sha256=store.sha(raw_witness),original_clocks=original_clocks)


def bind_capture(registered, choice, population, restored, *, storage, capture_id,
        role_catalog, frozen_schedule, authenticate, at, relocated_replays=()):
    """Read only parent-authenticated owned archives. All raw rows stay intact.

    A missing durability proof is retained as a metadata-only pending capture;
    it grants no private-body read, grade, or successful-forecast authority.
    """
    require(type(population) is Population, "LIVE_POPULATION_REQUIRED"); population.verify()
    choice.verify(registered, state.utc(at)); pop = population.document
    require(pop["epoch_sha256"] == registered.epoch.sha256 and pop["choice_sha256"] == choice.sha256
        and pop["role_catalog_sha256"] == state.digest(role_catalog)
        and store.HASH.fullmatch(str(capture_id)), "EXACT_CAPTURE_POPULATION_SCOPE")
    is_retained=type(restored) is dict and restored.get('schema_version') == retained.VERSION+'-result'
    require(type(restored) is dict and (is_retained or restored.get("schema_version") == archive.VERSION+"-restored"
        and restored.get("state") in {"PRIVATE_CAPTURE_RESTORED", "PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED", "PRIVATE_FAILURE_ARCHIVE_RESTORED"}
        and restored.get("scope_qualified_for_publication") is restored.get("public_export_authorized") is False),
        "PARENT_AUTHENTICATED_PRIVATE_CAPTURE_RESTORATION_REQUIRED")
    require(type(frozen_schedule) is list and 0 < len(frozen_schedule) <= 32
        and len({r["website_game_id"] for r in frozen_schedule}) == len(frozen_schedule)
        and len({r["game_id"] for r in frozen_schedule}) == len(frozen_schedule)
        and all((r["season"], r["week"]) == (choice.document["slate"]["season"], choice.document["slate"]["week"])
            for r in frozen_schedule), "COMPLETE_FROZEN_WEEK_SCHEDULE_REQUIRED")
    schedule_identity = state.digest(sorted((r["game_id"], state.utc(r["kickoff_utc"]).isoformat()) for r in frozen_schedule))
    require(schedule_identity == choice.document["slate"]["schedule_identity_sha256"]
        and len(frozen_schedule) == choice.document["slate"]["scheduled_games"], "FULL_WEEK_NOT_REMAINING_SUBSET_FINALITY")
    _authenticate(authenticate, "QUALIFIED_RETAINED_CAPTURE_RESTORATION" if is_retained else "QUALIFIED_CAPTURE_RESTORATION", dict(restored=restored,
        population=pop, capture_id=capture_id, roles=role_catalog, schedule=frozen_schedule,
        relocated_replays=relocated_replays), at)
    base = dict(capture_id=capture_id, epoch_sha256=registered.epoch.sha256, population=pop,
        restoration_schema=restored['schema_version'],restoration_state=restored['state'],
        choice=choice.document, roles=role_catalog, schedule=frozen_schedule,
        archive_index_sha256=restored.get("index_sha256"), aliases=restored["aliases"],
        source_proof_sha256=state.digest(restored), catalog=epoch.artifact_catalog(registered.epoch, *relocated_replays),
        opportunities=[], forecasts=[], selected=[], slots=[], known_by=None, ready=False,
        pending_reason="PENDING_CAPTURE_DURABILITY")
    if is_retained:
        evidence=_retained_evidence(restored,storage,at)
        base.update(archive_index_sha256=evidence['index_sha256'],retained_evidence=evidence)
        known_by=evidence['known_by']
    else:
        proofs = restored.get("exporter_proofs") or restored.get("restore_proofs") or []
        if restored.get("captured_bundle_hashes_restored") is not True or not proofs:
            return Capture(base, _KEY)
        clocks = [p["created_at_utc"] for p in proofs]
        witness = restored.get("restorer_witness") or {}
        if witness.get("actual_completed_at"): clocks.append(witness["actual_completed_at"])
        known_by = max(clocks, key=state.utc)
    require(state.utc(known_by) <= state.utc(at), "ACTUAL_CAPTURE_READBACK_CLOCK")
    meta = lambda name: _read_owned(storage, restored["aliases"][name], 2 << 20)
    source = meta("context/source.json")
    require(state.utc(pop["registered_at"]) <= state.utc(source["actual_source_started_at"])
        <= state.utc(source["actual_completed_at"]) <= state.utc(known_by), "POPULATION_REGISTERED_BEFORE_SOURCE_VALUES")
    require(meta("runtime/WEEKLY_CHOICE.json") == choice.document, "EXACT_ARCHIVED_FROZEN_CHOICE")
    import pyarrow.parquet as pq
    raw = _read_owned(storage, restored["aliases"]["runtime/queries.parquet"], 8 << 20, raw=True)
    parquet = pq.ParquetFile(io.BytesIO(raw))
    require(parquet.metadata.num_rows <= 1000, "FINITE_ORIGINAL_QUERIES")
    queries = parquet.read(columns=list(grading.METADATA)).to_pylist()
    for query in queries:
        for key in ("cutoff_utc", "kickoff_utc"): query[key] = state.utc(query[key]).isoformat()
    bridge = meta("runtime/IDENTITY_BRIDGE.json")
    opportunities = grading.opportunity_rows(queries, bridge, role_catalog)
    require(all(pop["assignments"].get(q["game_id"]) == capture_id
        and state.utc(q["cutoff_utc"]) == state.utc(choice.document["slate"]["game_cutoffs"][q["game_id"]]) for q in queries),
        "ONLY_PREASSIGNED_CAPTURE_PER_GAME_NO_REPEATED_HORIZON")
    slots = meta("runtime/CANDIDATES.json")["slots"]
    require(len(slots) == 18 and [(s["target"], s["method_id"]) for s in slots] == [(t,m) for t,_,m in cp.JOBS],
        "COMPLETE_FIXED18_STATUS_CENSUS_REQUIRED")
    budget = [0]; forecast_parts = []; receipts = {}
    for slot in slots:
        target, method = slot["target"], slot["method_id"]
        name = f"runtime/candidates/{target}/{method}.jsonl.gz"
        receipt = slot.get("persistence")
        if name not in restored["aliases"]:
            require(slot["state"] != "CAPTURED", "SUCCESSFUL_SLOT_MISSING_ORIGINAL_BODY"); continue
        rows = _rows(storage, restored["aliases"][name], maximum=1000, budget=budget)
        require(len(rows) == slot["issued_rows"] and (receipt is None or receipt["binding"]["sha256"] == restored["aliases"][name]["sha256"]),
            "FULL_ORIGINAL_CANDIDATE_COMPLETION_REQUIRED")
        require(all(r["category"] == target and r["method_id"] == method for r in rows), "EXACT_ORIGINAL_CANDIDATE_SLOT")
        if slot["state"] == "CAPTURED":
            require(type(receipt) is dict and receipt["state"] == "PERSISTED" and receipt["rows"] == len(rows)
                and slot["expected_rows"] == len(queries) == len(rows)
                and receipt["binding"]["bytes"] == restored["aliases"][name]["bytes"]
                and meta(name.removesuffix(".jsonl.gz")+".jsonl.completion.json") == receipt
                and state.utc(receipt["persist_started_at"]) <= state.utc(receipt["completed_at"])
                and all(state.utc(r["issued_at"]) <= state.utc(receipt["completed_at"]) < state.utc(r["cutoff_utc"]) for r in rows),
                "EXACT_SUCCESSFUL_SLOT_COMPLETION_NO_CLOCK_REPAIR")
        forecast_parts.append(rows); receipts[target,method] = receipt
    control_ref = restored["aliases"].get("r0/control_forecast_rows.json")
    if control_ref:
        control_body = _read_owned(storage, control_ref, 8 << 20, raw=True)
        controls = _JSONStream(io.BytesIO(control_body), 8 << 20, paged_keys=("rows",)).load()["rows"]
        del control_body
        require(len(controls) <= 18000 and all(r["method_id"] == "R0" for r in controls), "EXACT_ORIGINAL_R0_CONTROL_ROWS")
        control_completion = meta("r0/control_completion.json")
        require(control_completion["schema_version"] == "audit-reference-capture-v1-control-completion"
            and control_completion["forecast_binding"]["sha256"] == control_ref["sha256"]
            and control_completion["forecast_binding"]["bytes"] == control_ref["bytes"]
            and all(state.utc(r["issued_at"]) <= state.utc(control_completion["body_persist_completed_at"]) < state.utc(r["cutoff_utc"]) for r in controls),
            "EXACT_ARCHIVED_ORIGINAL_R0_CONTROL_COMPLETION")
        forecast_parts.append(controls)
    forecasts = _PagedRows.join(forecast_parts)
    selected_ref = restored["aliases"].get("runtime/selected.jsonl.gz")
    selected = _rows(storage, selected_ref, maximum=5000, budget=budget) if selected_ref else []
    # Exact source bodies remain separately archived. These checks never repair
    # old receipts or infer missing rows/zeros/fit clocks.
    # Runtime retains all queries in every slot, even outside modeled roles.
    # Keep that full body census separate from the primary-role P2 projection.
    offered = {}
    for query in queries:
        for target in cp.TARGETS:
            identity = selector.offered_id(dict(query,category=target))
            offered[identity] = dict(query,original_game_id=query["game_id"],target=target)
    seen = set()
    for row in chain(forecasts, selected):
        control = row["method_id"] == "R0"
        require(not {"actual", "label", "loss", "brier", "crps"} & set(row)
            and row.get("correction_epoch_sha256") == registered.epoch.sha256
            and row.get("evidence_lane") == "original_pregame"
            and (row.get("scientific_qualification") is False or control and "scientific_qualification" not in row and row.get("public_release") is False)
            and row["offered_id"] in offered, "ONLY_ORIGINAL_CURRENT_EPOCH_FORECASTS")
        original = offered[row["offered_id"]]
        require(all(row[k] == original[k if k != "game_id" else "original_game_id"] for k in ("player_id", "game_id", "category") if k != "category")
            and row["category"] == original["target"]
            and row["position"] == original["position"]
            and (row["season"],row["week"],row["slate_id"],row["horizon"]) == (original["season"],original["week"],choice.document["slate"]["slate_id"],"player_game")
            and state.utc(row["kickoff_utc"]) == state.utc(original["kickoff_utc"])
            and state.utc(row["cutoff_utc"]) == state.utc(original["cutoff_utc"])
            and (control or state.utc(source["actual_completed_at"]) <= state.utc(row["source_capture_completed_at"]))
            and state.utc(pop["registered_at"]) <= state.utc(row["source_capture_completed_at"]) <= state.utc(row["issued_at"]) < state.utc(row["cutoff_utc"])
            < state.utc(row["kickoff_utc"]), "ORIGINAL_OFFER_IDENTITY_AND_CLOCKS")
        if row["position"] not in role_catalog[row["category"]]["modeled_roles"]:
            require(row["operational_eligible"] is False, "OUTSIDE_MODELED_ROLES_RETAINED_INELIGIBLE")
        key = row["offered_id"], row["method_id"]
        require(key not in seen, "DUPLICATE_CAPTURE_FORECAST_NOT_AN_EXTRA_GAME"); seen.add(key)
    complete = restored["state"] != "PRIVATE_FAILURE_ARCHIVE_RESTORED" and restored.get("validation",{}).get("qualified_selected") is True
    complete = complete and all(s["state"] == "CAPTURED" and s["failure"] is None and s["attempt_qualified"] is True
        and s["expected_rows"] == s["issued_rows"] for s in slots)
    if complete:
        terminal = meta("runtime/FINISHED.json"); completion = meta("runtime/selected.jsonl.completion.json")
        require(terminal["schema_version"] == "audit-weekly-runtime-v1-result" and terminal["state"] == "PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE"
            and terminal["epoch_sha256"] == registered.epoch.sha256 and terminal["choice_sha256"] == choice.sha256
            and terminal["selected"] == completion and completion["state"] == "PERSISTED"
            and completion["rows"] == len(selected) and completion["binding"]["sha256"] == selected_ref["sha256"]
            and completion["binding"]["bytes"] == selected_ref["bytes"]
            and all(state.utc(row["issued_at"]) <= state.utc(completion["completed_at"]) < state.utc(row["cutoff_utc"]) for row in selected)
            and state.utc(completion["completed_at"]) <= state.utc(terminal["actual_completed_at"]) <= state.utc(known_by),
            "EXACT_NEW_RUNTIME_SELECTED_COMPLETION_REQUIRED")
    base.update(opportunities=_PagedRows(opportunities), forecasts=forecasts, selected=selected, slots=slots,
        known_by=known_by, ready=bool(complete), pending_reason=None if complete else "PARTIAL_CAPTURE_NEVER_QUALIFIES",
        source_started_at=source["actual_source_started_at"], source_completed_at=source["actual_completed_at"])
    del opportunities, queries, bridge, offered, seen, parquet, raw
    if complete: _check_selected(base, registered, choice, relocated_replays, at)
    return Capture(base, _KEY)


def _check_selected(capture, registered, choice, replays, at):
    local = deepcopy(capture); local.update(known_by=capture["source_completed_at"],ready=True)
    require({r["offered_id"] for r in capture["selected"]} ==
        {o["offered_id"] for o in capture["opportunities"] if o["primary_role"]}, "ALL_SELECTED_PRIMARY_OPPORTUNITIES_REQUIRED")
    selections = {s["decision"]["category"]:s for s in choice.document["choice"]["selections"]}
    versions = epoch.selected_versions(registered,choice,relocated_replays=replays,now=state.utc(at))["rows"]
    allowed = {(v["category"],v["procedure_version"],v["model_version"]) for v in versions}
    for category in cp.TARGETS:
        offers,forecasts,decisions,_,catalog,_ = _project([local],registered,category=category,include_selected=False)
        panel = selector.Panel(dict(schema_version=selector.VERSION,offers=offers,forecasts=forecasts,
            outcomes=[],decisions=decisions,weeks=[]),catalog)
        for row in _category_rows(capture["selected"], category):
            selected = selections[row["category"]]; components = row["components"]
            require(row["method_id"] == "P2_SELECTED" and row["selection_sha256"] == state.digest(selected), "ORIGINAL_FROZEN_SELECTED_RECIPE")
            if row["forecast_value"] is None:
                require(not components and row["operational_eligible"] is False, "HONEST_SELECTED_ABSTENTION"); continue
            reference = catalog["categories"][row["category"]]["reference_id"]
            require((row["category"],row["procedure_version"],row["model_version"]) in allowed
                and len(components) == len(selected["members"])
                and all(c["weight"] == m["weight"] and c["method_id"] in {m["method_id"],reference} for c,m in zip(components,selected["members"]))
                and state.digest([(c["method_id"],c["model_version"],c["weight"]) for c in components]) == row["model_version"]
                and math.fsum(c["value"]*c["weight"] for c in components) == row["forecast_value"], "NO_REWEIGHT_RESELECTION_OR_INVENTED_SELECTED_VALUE")
            if row["category"] == "anytime_td" and len(components) == 2 and any(c["method_id"] == reference for c in components):
                require(all(c["method_id"] == reference for c in components), "ORIGINAL_ATOMIC_TD_REFERENCE_FALLBACK")
            for component in components:
                original = panel.forecasts.get((row["offered_id"],component["method_id"]))
                require(original is not None and panel.eligible(component["method_id"],panel.offers[row["offered_id"]],"original_pregame")
                    and original["forecast_value"] == component["value"] and original["model_version"] == component["model_version"]
                    and state.utc(original["issued_at"]) <= state.utc(row["issued_at"]), "EXACT_ORIGINAL_SELECTED_COMPONENTS")
        del panel, forecasts


def provider_request(captures, *, at):
    """Bounded completed-game metadata for the parent's existing E7 collector.

    Callback acquisition must retain actual body/status SHA, publication clock
    (or explicit None), observed/capture clocks and finality. No retry here.
    """
    require(type(captures) is list and 0 < len(captures) <= LIMITS["captures"], "BOUNDED_TYPED_CAPTURE_LIST")
    games = {}; offers = {}
    for capture in captures:
        require(type(capture) is Capture, "LIVE_CAPTURE_REQUIRED"); capture.verify()
        for row in capture.document["schedule"]:
            if state.utc(row["kickoff_utc"]) < state.utc(at):
                games[row["season"],row["week"],row["website_game_id"]] = row
        for row in capture.document["opportunities"]:
            if state.utc(row["kickoff_utc"]) < state.utc(at): offers[row["offered_id"]] = row
    require(len(games) <= LIMITS["games"] and len(offers) <= LIMITS["opportunities"], "FINITE_OPERATIONAL_OUTCOME_REQUEST")
    return dict(schema_version=VERSION+"-provider-request", scope="FIXED_COMPLETED_GAME_OPERATIONAL_GRADING_ONLY",
        source_policy_sha256=cp.POLICY_SHA, as_of=state.utc(at).isoformat(), games=list(games.values()),
        opportunities=list(offers.values()), retries=0, fits=0, research_or_tuning=False)


def bind_observations(captures, document, *, authenticate, at):
    request = provider_request(captures, at=at)
    keys = {"schema_version", "source_policy_sha256", "captured_at", "observations", "finality"}
    require(type(document) is dict and set(document) == keys and document["schema_version"] == VERSION+"-provider-observations"
        and document["source_policy_sha256"] == cp.POLICY_SHA
        and type(document["observations"]) is list and len(document["observations"]) <= LIMITS["observation_rows"]
        and type(document["finality"]) is list and len(document["finality"]) <= 18
        and state.utc(document["captured_at"]) <= state.utc(at), "CLOSED_BOUNDED_OPERATIONAL_OBSERVATIONS_REQUIRED")
    _authenticate(authenticate, "COMPLETED_GAME_PROVIDER_OBSERVATIONS", dict(request=request, observations=document), at)
    offered = {(o["player_id"],o["game_id"],o["target"]):o for o in request["opportunities"]}
    games = {"espn:"+r["website_game_id"]:r for r in request["games"]}; finals = {}
    for proof in document["finality"]:
        require(set(proof) == {"season","week","games","status_source_sha256","observed_at"}
            and store.HASH.fullmatch(str(proof["status_source_sha256"])) and len(proof["games"]) <= 32
            and state.utc(proof["observed_at"]) <= state.utc(document["captured_at"]), "EXACT_PROVIDER_FINALITY_OBSERVATION")
        for game in proof["games"]:
            require(set(game) == {"game_id","kickoff_utc","home","away","final"} and type(game["final"]) is bool
                and game["game_id"] in games, "ONLY_COMPLETED_REGISTERED_GAME_STATUS")
            original = games[game["game_id"]]
            require((proof["season"],proof["week"]) == (original["season"],original["week"])
                and state.utc(game["kickoff_utc"]) == state.utc(original["kickoff_utc"])
                and {game["home"],game["away"]} == {original["home"],original["away"]}
                and state.utc(game["kickoff_utc"]) < state.utc(proof["observed_at"]), "EXACT_FINALITY_IDENTITY_AND_CLOCK")
            require(game["game_id"] not in finals, "DUPLICATE_FINALITY_GAME"); finals[game["game_id"]] = game["final"]
    required = {"player_id","game_id","target","actual","participation_state","source","source_sha256","status_sha256","observed_at","source_timestamp"}
    optional = {"identity_quarantined","scoring_id","period"}
    for row in document["observations"]:
        require(required <= set(row) <= required | optional
            and (row["player_id"],row["game_id"],row["target"]) in offered and finals.get(row["game_id"]) is True,
            "FIXED_OPERATIONAL_LABELS_ONLY_AFTER_GENUINE_GAME_FINAL")
        require(row["participation_state"] in {"played","DNP","unknown"}
            and (row["actual"] is None or type(row["actual"]) in (int,float) and math.isfinite(row["actual"]))
            and (row["participation_state"] == "played" or row["actual"] is None)
            and all(store.HASH.fullmatch(str(row[k])) for k in ("source_sha256","status_sha256"))
            and type(row["source"]) is str and 0 < len(row["source"]) <= 128
            and state.utc(games[row["game_id"]]["kickoff_utc"]) < state.utc(row["observed_at"])
            <= state.utc(document["captured_at"]), "EXPLICIT_PARTICIPATION_SOURCE_AND_ACTUAL_CAPTURE_CLOCKS")
        if row["source_timestamp"] is not None:
            require(state.utc(games[row["game_id"]]["kickoff_utc"]) < state.utc(row["source_timestamp"])
                <= state.utc(row["observed_at"]), "HONEST_PROVIDER_PUBLICATION_CLOCK_NOT_LOCAL_ARRIVAL")
    # The authenticated observation bytes remain exact. Avoid a second full
    # live provider graph while grading retains the caller's original capture.
    return Observations(dict(document, capture_ids=sorted(c.sha256 for c in captures)), _KEY)


def acquire(captures, *, collect, authenticate, clock=now):
    """One bounded parent E7 callback. Preserve its failure; never retry it."""
    stamp = state.utc(clock()); request = provider_request(captures,at=stamp)
    require(callable(collect), "EXISTING_E7_COLLECTOR_CALLBACK_REQUIRED")
    document = collect(deepcopy(request))
    return bind_observations(captures,document,authenticate=authenticate,at=state.utc(clock()))


def _category_rows(rows, category):
    if isinstance(rows, _PagedRows): return rows.category_rows(category)
    return (r for r in rows if category is None or r["category"] == category)


def _project(captures, registered, *, category=None, include_selected=True):
    offers = {}; forecasts = set(); decisions = {}; schedule = {}; raw_selected = []; catalogs = []
    forecast_pages = []; pending_forecasts = []
    for capture in captures:
        catalogs.append(capture["catalog"])
        for row in capture["schedule"]:
            key = row["season"],row["week"],row["website_game_id"]
            require(key not in schedule or schedule[key] == row, "FROZEN_FULL_WEEK_SCHEDULE_CHANGED")
            schedule[key] = row
        for selected in capture["choice"]["choice"]["selections"]:
            row = dict(selected["decision"], correction_epoch_sha256=registered.epoch.sha256)
            key = row["category"],row["season"],row["week"],row["slate_id"]
            require(key not in decisions or decisions[key] == row, "ONE_FROZEN_WEEKLY_P2_CHOICE_NO_RESELECTION")
            decisions[key] = row
        opportunity_by = {o["offered_id"]:o for o in capture["opportunities"]
            if o["primary_role"] and (category is None or o["target"] == category)}
        for identity, original in opportunity_by.items():
            row = dict(category=original["target"], season=original["season"], week=original["week"],
                slate_id=capture["choice"]["slate"]["slate_id"], player_id=original["player_id"],game_id=original["original_game_id"],
                horizon="player_game",cutoff_utc=original["cutoff_utc"],kickoff_utc=original["kickoff_utc"],
                offered_id=identity,correction_epoch_sha256=registered.epoch.sha256)
            require(identity not in offers, "REPEATED_CAPTURE_IS_NOT_AN_INDEPENDENT_OFFER")
            offers[identity] = row
        for raw in _category_rows(capture["forecasts"], category):
            identity, method = raw["offered_id"],raw["method_id"]
            if identity not in opportunity_by: continue
            spec = capture["catalog"]["catalog"]["methods"].get(method)
            if not spec or raw["model_version"] not in spec["model_versions"]: continue
            row = deepcopy(raw)
            for key in ("cutoff_utc", "kickoff_utc"): row[key] = state.utc(row[key]).isoformat()
            require(all(row[k] == v for k,v in offers[identity].items()), "ORIGINAL_FORECAST_OFFER_CONTRACT_CHANGED")
            if not capture["ready"] or capture["known_by"] is None or state.utc(capture["known_by"]) > state.utc(row["cutoff_utc"]):
                row.update(operational_eligible=False, grading_ineligible_reason="CAPTURE_PARTIAL_OR_DURABILITY_AFTER_INPUT_CUTOFF")
            key = identity, method
            require(key not in forecasts, "DUPLICATE_METHOD_ISSUANCE_NO_LAST_WRITE_WINS"); forecasts.add(key)
            pending_forecasts.append(row)
            if len(pending_forecasts) == 64:
                forecast_pages.append(_PagedRows(pending_forecasts)); pending_forecasts = []
        if include_selected:
            for row in _category_rows(capture["selected"], category):
                if row["offered_id"] in opportunity_by: raw_selected.append((capture,row))
    catalog = epoch.artifact_catalog(registered.epoch)["catalog"]
    for item in catalogs:
        require(selector.procedure_catalog(item["catalog"]) == selector.procedure_catalog(catalog), "UNCHANGED_EFFECTIVE_EPOCH_PROCEDURES")
        for method,spec in item["catalog"]["methods"].items():
            catalog["methods"][method]["model_versions"] = sorted(set(catalog["methods"][method]["model_versions"] + spec["model_versions"]))
    if pending_forecasts: forecast_pages.append(_PagedRows(pending_forecasts))
    # Panel copies every forecast. Keep its exact input order/values in bounded
    # immutable pages rather than retaining another complete dictionary graph.
    return list(offers.values()),_PagedRows.join(forecast_pages),list(decisions.values()),list(schedule.values()),catalog,raw_selected


def _write_snapshot(storage, output, document):
    # Preserve gzip.compress(..., mtime=0) bytes, including the host Python's
    # header, while feeding one continuous deflate stream bounded chunks.
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    encoded = io.BytesIO(); encoded.write(gzip.compress(b"", mtime=0)[:10])
    total = crc = 0
    for chunk in _canonical_chunks(document):
        total += len(chunk)
        require(total <= LIMITS["decoded_bytes"], "FINITE_FULL_GRADING_SNAPSHOT")
        crc = zlib.crc32(chunk, crc); encoded.write(compressor.compress(chunk))
        require(encoded.tell() <= LIMITS["encoded_bytes"], "FULL_GRADING_SNAPSHOT_ASSET_BOUND_NO_TRUNCATION")
    encoded.write(compressor.flush()); encoded.write(struct.pack("<LL", crc, total))
    require(encoded.tell() <= LIMITS["encoded_bytes"], "FULL_GRADING_SNAPSHOT_ASSET_BOUND_NO_TRUNCATION")
    body = encoded.getvalue()
    path = Path(output)/"GRADING_SNAPSHOT.json.gz"
    storage.write_bytes(path, body)
    owned = storage.validate_reference(path, store.sha(body))
    require(owned["bytes"] == len(body), "EXACT_WRITTEN_GRADING_SNAPSHOT_BYTES")
    return {key:owned[key] for key in ("path", "bytes", "sha256")}


def _record_body(document, maximum):
    """The unchanged state.save canonical digest and gzip bytes, streamed."""
    digest = hashlib.sha256(); compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    encoded = io.BytesIO(); encoded.write(gzip.compress(b"", mtime=0)[:10])
    total = crc = 0
    for chunk in _canonical_chunks(document):
        digest.update(chunk); total += len(chunk); crc = zlib.crc32(chunk, crc)
        encoded.write(compressor.compress(chunk))
        if encoded.tell() > maximum:
            raise RuntimeError("durable evidence cap reached; no evidence deleted")
    encoded.write(compressor.flush()); encoded.write(struct.pack("<LL", crc, total & 0xffffffff))
    if encoded.tell() > maximum:
        raise RuntimeError("durable evidence cap reached; no evidence deleted")
    return digest.hexdigest(), encoded.getvalue()


def _same_record(path, document):
    # Preserve the original literal decompressed-byte equality check, including
    # valid older gzip headers, without a second complete JSON string/graph.
    with gzip.open(path, "rb") as reader:
        for chunk in _canonical_chunks(document):
            if reader.read(len(chunk)) != chunk: raise ValueError("conflicting immutable record")
        if reader.read(1): raise ValueError("conflicting immutable record")


@contextmanager
def _compact_scans(storage):
    """Same full quota scan, visiting an overlapping root's files only once.

    The registry and every root retain their original checks. The original
    scanner still checks the identical union of files, blob hashes, inode/link
    counts and byte limits under the same flock. Only duplicate tree walks are
    removed; the returned root census and persistent registry are unchanged.
    """
    original = storage._scan
    if getattr(original, "_grade_root_cover", False):
        yield; return
    prior = storage.__dict__.get("_scan")
    def scan():
        with storage._locked():
            roots = storage._roots
            for directory in roots:
                _no_symlinks(directory)
                if directory.exists() and not directory.is_dir():
                    raise StorageIntegrityError("managed root must be a directory")
            cover = []
            for directory in sorted(roots, key=lambda p:(len(p.parts), str(p))):
                if not any(directory.is_relative_to(parent) for parent in cover): cover.append(directory)
            storage._roots = cover
            try: result = original()
            finally: storage._roots = roots
            result["roots"] = [str(directory) for directory in roots]
            return result
    scan._grade_root_cover = True
    storage._scan = scan
    try: yield
    finally:
        if prior is None: storage.__dict__.pop("_scan", None)
        else: storage._scan = prior


def _scanned_storage(function):
    @wraps(function)
    def call(*args, **kwargs):
        storage = kwargs["storage"] if "storage" in kwargs else args[0]
        with _compact_scans(storage): return function(*args, **kwargs)
    return call


@contextmanager
def _record_batch(storage, root):
    """Only grade's immutable state.save seam; resolver and row order unchanged.

    One original global quota flock covers the complete cohort. Initial and
    final full scans retain every ownership/hardlink/blob check. Exact incoming
    bytes are reserved against the initial physical count before each new blob;
    no other cooperative writer can consume that reservation under the flock.
    Every alias is then checked against its physical SHA before returning.
    Failures retain every published record and partial incoming file.
    """
    root = Path(root).absolute(); collector = root/"collector"
    roots = (root, collector)
    for directory in roots: storage.register_root(directory)
    with storage._locked():
        previous, previous_records, previous_digest = state.save, state.records, state.digest
        refs = {}
        try:
            storage._refresh(); usage = storage._scan()
            physical = usage["physical_bytes"]
            logical = {directory:sum(p.stat().st_size for p in directory.rglob("*")
                if p.is_file() and p.name != ".writer.lock") for directory in roots}
            def save(directory, kind, document, max_bytes=200 * 1024 * 1024):
                nonlocal physical
                directory = Path(directory).absolute()
                require((directory == collector and kind == "outcomes") or
                    (directory == root and kind in {"weekly_versions", "weekly_completions"}),
                    "EXACT_GRADING_RECORD_BATCH_NAMESPACE")
                key = _digest(document)
                path = storage._check(directory/kind/(key+".json.gz"))
                if path.exists():
                    _same_record(path, document)
                    refs[str(path)] = _digest_file(path)
                    return key
                encoded_key, body = _record_body(document, max_bytes)
                require(encoded_key == key, "GRADING_RECORD_CHANGED_DURING_ENCODING")
                if logical[directory] + len(body) > max_bytes:
                    raise RuntimeError("durable evidence cap reached; no evidence deleted")
                sha = store.sha(body); blob = storage.blob_root/sha
                if blob.exists(): storage._verify_blob(blob)
                else:
                    if physical + len(body) > storage.limit_bytes:
                        raise StorageQuotaError("incoming bytes exceed shared operational quota before write; evidence preserved")
                    temporary, descriptor = storage._temporary(storage.control_root, ".incoming-")
                    try:
                        storage._write_all(descriptor, body); os.fsync(descriptor)
                    finally: os.close(descriptor)
                    blob = storage._publish_blob(temporary, sha)
                    physical += len(body)
                storage._alias(blob, path, False)
                for ancestor in roots:
                    if path.is_relative_to(ancestor): logical[ancestor] += len(body)
                refs[str(path)] = sha
                return key
            def records(directory, kind):
                directory = Path(directory).absolute(); pool = {}
                require((directory == collector and kind == "outcomes") or
                    (directory == root and kind in {"weekly_versions", "weekly_completions"}),
                    "EXACT_GRADING_RECORD_BATCH_NAMESPACE")
                for path in sorted((directory/kind).glob("*.json.gz")):
                    path = storage._check(path); info = path.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o222:
                        raise StorageIntegrityError("record is not an immutable regular file")
                    sha = _digest_file(path); blob = storage.blob_root/sha
                    if info.st_mode & 0o222 or not blob.exists() or not os.path.samestat(info, blob.lstat()):
                        raise StorageIntegrityError("record is not an immutable owned blob alias")
                    storage._verify_blob(blob)
                    if str(path) in refs and refs[str(path)] != sha:
                        raise StorageIntegrityError("immutable grading record changed")
                    with gzip.open(path, "rb") as reader:
                        document = _JSONStream(reader, LIMITS["decoded_bytes"]).load()
                    if _digest(document) != path.name.removesuffix(".json.gz"):
                        raise ValueError(f"immutable record hash mismatch: {path}")
                    if _digest_file(path) != sha:
                        raise StorageIntegrityError("immutable grading record changed during readback")
                    refs[str(path)] = sha
                    yield dict(_freeze(document, pool))
            # operational_io owns the existing serializer lock and restores its
            # imported save aliases. All grade/resolver writes use state.save.
            state.save = save
            state.records = records
            state.digest = _digest
            yield
        finally:
            state.save = previous
            state.records = previous_records
            state.digest = previous_digest
            storage._refresh()
            if refs: validate_owned_references(storage, refs)
            else: storage._scan()


@_scanned_storage
def grade(registered, captures, batches, *, storage, output, previous=None, clock=now):
    """Append existing resolver revisions. Local completion grants NO durability.

    Previous pending snapshots are allowed so interruptions/failures survive.
    Existing qualified version clocks are preserved in known_versions.
    """
    started = time.monotonic(); CPU = time.process_time(); stamp = state.utc(clock())
    registered.verify(stamp)
    require(type(captures) is list and len(captures) <= LIMITS["captures"] and type(batches) is list and len(batches) <= 36,
        "BOUNDED_CAPTURE_AND_OBSERVATION_BATCHES")
    old = None
    if previous is not None:
        require(type(previous) in {Snapshot,DurableHistory}, "LIVE_PREVIOUS_GRADING_STATE_REQUIRED"); previous.verify(); old = previous.document
        require(old["epoch_sha256"] == registered.epoch.sha256, "NO_LEGACY_OR_DIFFERENT_EPOCH_HISTORY_MERGE")
    retained = deepcopy(old["captures"] if old else []); ids = {c["capture_id"]:c for c in retained}
    for capture in captures:
        require(type(capture) is Capture, "LIVE_CAPTURE_REQUIRED"); capture.verify(); item = capture.document
        require(item["epoch_sha256"] == registered.epoch.sha256, "EXACT_CURRENT_EPOCH_CAPTURE_REQUIRED")
        require(item["capture_id"] not in ids or ids[item["capture_id"]] == item, "CAPTURE_ID_REUSE_OR_REISSUANCE_FORBIDDEN")
        if item["capture_id"] not in ids: retained.append(deepcopy(item)); ids[item["capture_id"]] = item
    require(0 < len(retained) <= LIMITS["captures"], "FINITE_RETAINED_CAPTURE_CENSUS")
    streams = {(c["population"]["stream_id"],c["population"]["role_catalog_sha256"]) for c in retained}
    require(len(streams) == 1, "NO_POPULATION_OR_ROLE_STREAM_MERGE")
    offer_ids = set(); forecast_count = 0
    for category in cp.TARGETS:
        offers,forecasts,decisions,schedule,_,_ = _project(retained, registered, category=category, include_selected=False)
        require(not offer_ids.intersection(o["offered_id"] for o in offers), "REPEATED_CAPTURE_IS_NOT_AN_INDEPENDENT_OFFER")
        offer_ids.update(o["offered_id"] for o in offers); forecast_count += len(forecasts)
        del offers, forecasts
    require(len(offer_ids) <= LIMITS["opportunities"] and forecast_count <= LIMITS["forecast_rows"], "FINITE_COMPLETE_EPOCH_HISTORY")
    del offer_ids
    output = archive.fresh(storage,output); root = output/"resolver"; storage.register_root(root)
    observation_parts = [old["collector_records"]] if old else []
    finality = deepcopy(old["finality_records"] if old else [])
    for batch in batches:
        require(type(batch) is Observations, "LIVE_PROVIDER_OBSERVATIONS_REQUIRED"); batch.verify()
        require(set(batch.document["capture_ids"]) <= {_digest(c) for c in retained}, "OUTCOMES_FROM_DIFFERENT_CAPTURE_SCOPE")
        observation_parts.append(batch.document["observations"]); finality.extend(deepcopy(batch.document["finality"]))
    require(sum(len(part) for part in observation_parts) <= LIMITS["revisions"], "FINITE_RETAINED_PROVIDER_REVISIONS")
    stream = dict(schema_version=grading.VERSION+"-stream",stream_id=next(iter(streams))[0],stream_kind="primary_daily",horizon_version=VERSION+"-exact-assignment-player-game")
    opportunities = [o for c in retained for o in c["opportunities"]]
    with operational_io(storage), _record_batch(storage, root):
        if old:
            for version in old["versions"]:
                state.save(root,"weekly_versions",version["snapshot"])
                state.save(root,"weekly_completions",version["completion"])
        state.append_outcomes(root/"collector",(deepcopy(row) for part in observation_parts for row in part))
        del observation_parts
        completed_opportunities = [o for o in opportunities if state.utc(o["kickoff_utc"]) < stamp]
        resolved = grading.append_resolved(root,stream,completed_opportunities,clock=clock)
        changed = resolved[1]; del resolved
        del opportunities, completed_opportunities
        collector = _PagedRows(state.records(root/"collector","outcomes"))
        completions = {v["snapshot_id"]:v for v in state.records(root,"weekly_completions")}
        versions = [dict(snapshot=v,completion=completions[_digest(v)]) for v in state.records(root,"weekly_versions")]
    completed = state.utc(clock()).isoformat()
    require(stamp <= state.utc(completed) and time.monotonic()-started <= LIMITS["wall_seconds"]
        and time.process_time()-CPU <= LIMITS["CPU_seconds"], "FINITE_OPERATIONAL_GRADING_ENVELOPE")
    # Newer observed status can withdraw an earlier finality claim. Conflicting
    # equal-clock receipts stay pending rather than choosing by arrival order.
    by = {}
    for proof in finality: by.setdefault((proof["season"],proof["week"]),[]).append(proof)
    latest = []
    for proofs in by.values():
        t = max(state.utc(p["observed_at"]) for p in proofs); same = [p for p in proofs if state.utc(p["observed_at"]) == t]
        if len({state.digest(p) for p in same}) == 1: latest.append(same[0])
    weeks,pending = grading.complete_weeks(latest,schedule,decisions,grade_completed_at=completed)
    usable = []
    for week in weeks:
        cohort = [c for c in retained if (c["choice"]["slate"]["season"],c["choice"]["slate"]["week"]) == (week["season"],week["week"])]
        complete_population = all(c["ready"] and set(c["population"]["assignments"].values()) <= set(ids) for c in cohort)
        if complete_population: usable.append(week)
        else: pending.append(dict(week,state="PENDING_COMPLETE_QUALIFIED_CAPTURE_POPULATION",grade_completed_at=None))
    weeks = usable
    week_revisions = deepcopy(old["week_revisions"] if old else [])
    prior_weeks = {}
    for week in week_revisions:
        key = selector._key(week)
        if key not in prior_weeks or week["revision"] > prior_weeks[key]["revision"]: prior_weeks[key] = week
    for index,week in enumerate(weeks):
        key = selector._key(week)
        available_versions = [(r["offered_id"],r["revision"]) for v in versions for r in v["snapshot"]["rows"]
            if (r["category"],r["season"],r["week"]) == key[:3]]
        fingerprint = state.digest(dict(decision=next(d for d in decisions if selector._key(d)==key),
            outcome_versions=sorted(available_versions),scheduled_games=week["scheduled_games"],all_games_final=True))
        old_week = prior_weeks.get(key)
        if old_week and old_week["grading_fingerprint"] == fingerprint: weeks[index] = old_week
        else:
            week.update(grading_fingerprint=fingerprint,revision=old_week["revision"]+1 if old_week else 1)
            week_revisions.append(deepcopy(week))
    document = dict(schema_version=VERSION+"-snapshot",epoch_sha256=registered.epoch.sha256,
        legacy_history_binding=deepcopy(registered.epoch.origin["history_binding"]),captures=retained,
        collector_records=collector,versions=versions,finality_records=finality,weeks=weeks,pending_weeks=pending,week_revisions=week_revisions,
        known_versions=deepcopy(old["known_versions"] if old else {}),known_weeks=deepcopy(old["known_weeks"] if old else {}),
        actual_completed_at=completed,new_revisions=changed,local_only=True,metadata_remote_durability_qualified=False,successful_forecast=False,
        scientific_qualification=False,public_release=False,fits=0,searches=0,code_pins=pins())
    for version in versions:
        version["snapshot"]["rows"] = _PagedRows(version["snapshot"]["rows"])
    ref = _write_snapshot(storage,output,document)
    result = Snapshot(document,_KEY); result.binding = ref; result._binding_sha256 = state.digest(ref)
    return result


@_scanned_storage
def restore_snapshot(storage, ref, registered, *, authenticate, at):
    """Authenticate a parent-restored grading snapshot before decoding bytes."""
    require(type(registered) is epoch.RegisteredEpoch, "TYPED_REGISTERED_EPOCH_REQUIRED"); registered.verify(state.utc(at))
    _authenticate(authenticate,"QUALIFIED_PREVIOUS_GRADING_SNAPSHOT",dict(binding=ref,epoch_sha256=registered.epoch.sha256),at)
    encoded = _read_owned(storage,ref,LIMITS["encoded_bytes"],raw=True)
    doc = _unpack(encoded,LIMITS["decoded_bytes"])
    require(set(doc) == SNAPSHOT_KEYS and doc["schema_version"] == VERSION+"-snapshot" and doc["epoch_sha256"] == registered.epoch.sha256
        and doc["legacy_history_binding"] == registered.epoch.origin["history_binding"] and doc["code_pins"] == pins(),
        "EXACT_PARENT_RESTORED_CURRENT_EPOCH_GRADING_STATE")
    require(0 < len(doc["captures"]) <= LIMITS["captures"] and len(doc["collector_records"]) <= LIMITS["revisions"]
        and len(doc["versions"]) <= LIMITS["revisions"] and doc["fits"] == doc["searches"] == 0
        and doc["metadata_remote_durability_qualified"] is False
        and doc["public_release"] is doc["scientific_qualification"] is doc["successful_forecast"] is False,
        "FINITE_CLOSED_RESTORED_GRADING_STATE")
    result = Snapshot(doc,_KEY); result.binding = deepcopy(ref); result._binding_sha256 = state.digest(ref); return result


@_scanned_storage
def persist_snapshot(snapshot, *, storage, output):
    """Save exact local metadata for parent checkpointing, without a POST."""
    require(type(snapshot) in {Snapshot,DurableHistory}, "LIVE_GRADING_STATE_REQUIRED"); snapshot.verify()
    output = archive.fresh(storage,output)
    return _write_snapshot(storage,output,snapshot.document)


def retained_captures(snapshot, registered, *, at):
    """Reuse original frozen captures after parent-authenticated state restore.

    No original path, model, forecast or source is reopened/refreshed here.
    Only subsequent provider observations receive new acquisition clocks.
    """
    require(type(snapshot) in {Snapshot,DurableHistory}, "LIVE_RESTORED_GRADING_STATE_REQUIRED"); snapshot.verify()
    registered.verify(state.utc(at))
    require(snapshot.document["epoch_sha256"] == registered.epoch.sha256, "EXACT_RETAINED_CAPTURE_EPOCH")
    return [Capture(c,_KEY) for c in snapshot.document["captures"]]


def confirm_durable(snapshot, proof, *, registered, authenticate, at):
    """Parent proves exact current checkpoint bytes through a distinct reader.

    This creates a typed, in-process authority. Its newly created metadata is
    NOT itself asserted remotely durable; parent archives it with later state.
    """
    require(type(snapshot) is Snapshot, "LOCAL_GRADING_SNAPSHOT_REQUIRED"); snapshot.verify()
    fields = {"schema_version","snapshot_sha256","restored_body_sha256","known_by_at","producer","reader","proof_sha256"}
    require(type(proof) is dict and set(proof) == fields and proof["schema_version"] == VERSION+"-durability"
        and proof["snapshot_sha256"] == snapshot.sha256 and proof["restored_body_sha256"] == snapshot.binding["sha256"]
        and store.HASH.fullmatch(str(proof["proof_sha256"]))
        and state.utc(snapshot.document["actual_completed_at"]) <= state.utc(proof["known_by_at"]) <= state.utc(at),
        "GENUINE_FRESH_READER_GRADING_DURABILITY_REQUIRED")
    identity_fields = {"execution_lane","repository","run_id","run_attempt","source_sha","process_identity","job_id","api_job_id","permission","workflow_ref"}
    for identity in (proof["producer"],proof["reader"]):
        require(type(identity) is dict and set(identity) == identity_fields
            and identity["execution_lane"] == "github_actions" and identity["repository"] == store.REPO
            and type(identity["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",identity["run_id"])
            and type(identity["run_attempt"]) is int and identity["run_attempt"] == 1
            and re.fullmatch(r"[a-f0-9]{40}",str(identity["source_sha"]))
            and store.HASH.fullmatch(str(identity["process_identity"])) and type(identity["api_job_id"]) is int and identity["api_job_id"] > 0
            and re.fullmatch(r"[A-Za-z0-9_-]+",str(identity["job_id"])) and identity["permission"] == "write"
            and re.fullmatch(re.escape(store.REPO)+r"/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+",str(identity["workflow_ref"])),
            "CLOSED_GENUINE_GRADING_JOB_IDENTITY_REQUIRED")
    writer,reader = proof["producer"],proof["reader"]
    require(all(writer[k] == reader[k] for k in ("run_id","run_attempt","source_sha","workflow_ref"))
        and all(writer[k] != reader[k] for k in ("job_id","api_job_id","process_identity")),
        "DISTINCT_CURRENT_RUN_GRADING_FRESH_READER_REQUIRED")
    _authenticate(authenticate,"FRESH_READER_GRADING_DURABILITY",proof,at)
    doc = deepcopy(snapshot.document); registered.verify(state.utc(at))
    for version in doc["versions"]:
        sid = _digest(version["snapshot"])
        doc["known_versions"].setdefault(sid,dict(known_by_at=proof["known_by_at"],proof_sha256=proof["proof_sha256"]))
    for week in doc["weeks"]:
        doc["known_weeks"].setdefault(state.digest(week),dict(known_by_at=proof["known_by_at"],proof_sha256=proof["proof_sha256"]))
    doc["local_only"] = False
    return DurableHistory(doc,_KEY)


def history(durable, registered, *, at):
    require(type(durable) is DurableHistory, "FRESH_DURABILITY_BOUND_HISTORY_REQUIRED"); durable.verify()
    doc = durable.document
    require(doc["epoch_sha256"] == registered.epoch.sha256, "EXACT_CURRENT_EPOCH_HISTORY")
    offers,forecasts,decisions,schedule,catalog,_ = _project(doc["captures"],registered,include_selected=False)
    ids = {o["offered_id"] for o in offers}; outcomes = []
    for version in doc["versions"]:
        known = doc["known_versions"].get(_digest(version["snapshot"]))
        if known is None: continue
        available = max(version["completion"]["persisted_completed_at"],known["known_by_at"],key=state.utc)
        for raw in version["snapshot"]["rows"]:
            if raw["offered_id"] in ids:
                outcomes.append(dict(raw,available_at=available,actual_known_at=available,
                    correction_epoch_sha256=registered.epoch.sha256))
    # Recovery can first qualify several previously LOCAL revisions together.
    # They have ONE real durable clock, not invented epsilon-separated clocks.
    # The causal Panel view exposes the latest then-known revision; all original
    # versions remain in the authenticated snapshot, explicitly identified here.
    simultaneous = {}
    for row in outcomes:
        simultaneous.setdefault((row["offered_id"],state.utc(row["available_at"])),[]).append(row)
    outcomes = []
    for rows in simultaneous.values():
        selected = max(rows,key=lambda r:r["revision"])
        if len(rows) > 1:
            selected = dict(selected,coqualified_prior_revisions=sorted(r["revision"] for r in rows if r is not selected))
        outcomes.append(selected)
    outcomes = _PagedRows(outcomes)
    simultaneous.clear()
    weeks = []
    for raw in doc["weeks"]:
        known = doc["known_weeks"].get(state.digest(raw))
        if known:
            row = dict(raw,grade_completed_at=max(raw["grade_completed_at"],known["known_by_at"],key=state.utc))
            if state.utc(row["grade_completed_at"]) < state.utc(at): weeks.append(row)
    bundle = dict(schema_version=selector.VERSION,offers=offers,forecasts=forecasts,outcomes=outcomes,decisions=decisions,weeks=weeks)
    selector.Panel(bundle,catalog)
    return dict(schema_version=epoch.VERSION+"-history",epoch_sha256=registered.epoch.sha256,
        legacy_history_binding=deepcopy(doc["legacy_history_binding"]),bundle=bundle)


def report(durable, registered, *, at):
    view = history(durable,registered,at=at)
    captures = durable.document["captures"]
    catalog = epoch.artifact_catalog(registered.epoch)["catalog"]
    for capture in captures:
        item = capture["catalog"]["catalog"]
        require(selector.procedure_catalog(item) == selector.procedure_catalog(catalog), "UNCHANGED_EFFECTIVE_EPOCH_PROCEDURES")
        for method, spec in item["methods"].items():
            catalog["methods"][method]["model_versions"] = sorted(set(catalog["methods"][method]["model_versions"] + spec["model_versions"]))
    def originals():
        for capture in captures:
            primary = {o["offered_id"] for o in capture["opportunities"] if o["primary_role"]}
            for row in capture["selected"]:
                if row["offered_id"] in primary: yield capture, row
    panel = selector.Panel(view["bundle"],catalog); groups = {}
    resolved = {selector._key(w) for w in view["bundle"]["weeks"]}
    for row in view["bundle"]["forecasts"]:
        offer = panel.offers[row["offered_id"]]
        if selector._key(offer) in resolved and panel.eligible(row["method_id"],offer,"original_pregame"):
            groups.setdefault((row["category"],row["method_id"]),[]).append(row)
    for capture,raw in originals():
        if capture["ready"] and state.utc(capture["known_by"]) <= state.utc(raw["cutoff_utc"]) and raw.get("operational_eligible") is True:
            offer = panel.offers[raw["offered_id"]]
            if selector._key(offer) in resolved: groups.setdefault((raw["category"],"P2_SELECTED"),[]).append(raw)
    metrics = []
    for (target,method),rows in sorted(groups.items()):
        issued = [dict(r,primary_metric=catalog["categories"][target]["primary_metric"],
            fallback_reason=r.get("fallback_reason",""),components=r.get("components",[])) for r in rows]
        scored = selector.evaluate(panel,issued,at)
        residuals = []
        for row in issued:
            out = panel.grade(row["offered_id"],at)
            if out and out["participation_state"] == "played" and panel.valid_actual(out.get("actual"),target) and row["forecast_value"] is not None:
                residuals.append(row["forecast_value"]-out["actual"])
        absolute = sorted(abs(v) for v in residuals)
        metrics.append(dict(category=target,method_id=method,primary_metric=catalog["categories"][target]["primary_metric"],
            **scored,signed_bias=math.fsum(residuals)/len(residuals) if residuals else None,
            original_primary_offers=sum(o["category"] == target for o in view["bundle"]["offers"]),
            absolute_error_p90_nearest_rank=absolute[math.ceil(.9*len(absolute))-1] if absolute else None,
            accuracy_claim=False))
    return dict(schema_version=VERSION+"-report",epoch_sha256=registered.epoch.sha256,metrics=metrics,
        candidate_slots=[dict(capture_id=c["capture_id"],slots=c["slots"],ready=c["ready"],pending_reason=c["pending_reason"]) for c in durable.document["captures"]],
        pending_weeks=durable.document["pending_weeks"],all_negative_weeks_retained=True,
        exact_PPR="BLOCKED_LABEL_CONTRACT",fits=0,searches=0,public_release=False,scientific_qualification=False)


def select_next(registered, durable, slate, previous_choice, *, full_schedule, authenticate, relocated_replays=(), clock=now):
    """Routine P2 uses the actual FULL new week, never an initial remainder."""
    stamp = state.utc(clock())
    fields = {"season","week","game_type","game_id","kickoff_utc"}
    require(type(full_schedule) is list and 0 < len(full_schedule) <= 32
        and all(set(r) == fields and r["game_type"] == "REG"
            and (r["season"],r["week"]) == (slate["season"],slate["week"]) for r in full_schedule),
        "EXACT_PARENT_FULL_NEXT_WEEK_SCHEDULE_REQUIRED")
    _authenticate(authenticate,"NEXT_FULL_WEEK_SLATE_BEFORE_VALUES",dict(slate=slate,full_schedule=full_schedule),stamp)
    from . import weekly_generic_producer as generic
    expected = generic.prepare_slate(full_schedule,season=slate["season"],week=slate["week"],game_cutoffs=slate["game_cutoffs"],now=stamp)
    require(slate == expected and expected["elapsed_games"] == 0, "ROUTINE_FULL_WEEK_DEADLINE_CANNOT_INHERIT_INITIAL_REMAINDER")
    view = history(durable,registered,at=stamp)
    return epoch.select_next_week(registered,view,slate,previous_choice,
        relocated_replays=relocated_replays,clock=lambda:stamp)
