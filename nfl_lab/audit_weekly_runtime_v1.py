"""Private zero-fit composition for an authenticated correction epoch.

The parent authenticates every input, current Actions authority and external
completion. Hashes/owned files are not substitutes for that authentication.
Prepare precedes current values. Acquire refreshes four E7 feeds in a fresh
directory; infer is offline. Nothing on import acquires, fits or publishes.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import hashlib
import math
import os
import re

from . import audit_weekly_epoch_v1 as epoch, audit_count_retained_v1 as retained
from . import audit_count_checkpoint_v1 as effective, private_draft_store as private
from . import weekly_generic_producer as generic, weekly_adaptive as selector
from . import audit_numerical_runtime_v1 as numerical
from .operational_storage import OperationalStorage
from .owned_reference_batch import validate_owned_references
from .state import canonical, digest, utc, now_utc

VERSION = "audit-weekly-runtime-v1"
HANDOFF = VERSION + "-private-handoff"
LIMITS = dict(generic.LIMITS)
ACQUISITION_LIMITS = dict(wall_seconds=420, CPU_seconds=300, RSS_bytes=1 << 30,
    address_space_bytes=4 << 30, numerical_threads=2, global_bytes=512 << 20,
    source_bytes=512 << 20, mutable_feeds=4, downloader_attempts_per_feed=3, invocations=1)
PIN_PATHS = tuple(sorted(set(retained.CURRENT_FILES) | {
    "nfl_lab/audit_weekly_epoch_v1.py", "nfl_lab/audit_weekly_runtime_v1.py",
    "tools/audit_weekly_runtime_v1.py", "nfl_lab/weekly_current_query.py",
    "nfl_lab/operational_sources.py", "nfl_lab/data.py", "nfl_lab/features.py",
    "nfl_lab/permitted_source_features.py", "nfl_lab/operational_io.py",
    "nfl_lab/weekly_current_inference.py", "nfl_lab/weekly_generic_producer.py",
    "nfl_lab/weekly_adaptive.py", "nfl_lab/weekly_source_read_batch.py", "tools/audit_process_guard_v1.py",
    "nfl_lab/audit_numerical_runtime_v1.py", "config/audit-weekly-numerical-runtime-v1.json"}))
CONFIG_KEYS = {"history_seasons", "allowed_periods", "freshness_seconds"}
BASE_CANDIDATE_KEYS = set("offered_id category season week slate_id horizon method_id model_version procedure_version product prediction_functional forecast_value metric player_id game_id team opponent position issued_at cutoff_utc kickoff_utc weekly_decision_cutoff_utc operational_eligible evidence_lane reference_stream fallback fallback_reason training_cutoff_utc training_max_available_utc source_policy_sha256 training_started_at training_completed_at source_capture_completed_at training_source_capture_completed_at feature_max_source_available_utc query_source_sha256 artifact_sha256 distribution_kind distribution_ref scientific_qualification publication_status".split())


class RuntimeErrorCode(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise RuntimeErrorCode(code)


def pins():
    root = Path(__file__).resolve().parents[1]
    return {name: private.sha(private.read_local(root/name, 2 << 20)) for name in PIN_PATHS}


def reason(error):
    code = str(error) if isinstance(error, RuntimeErrorCode) else "UPSTREAM_OPERATION_FAILED"
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "UPSTREAM_OPERATION_FAILED"


def read_owned(storage, ref, cap=2 << 20, *, raw=False):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap, "CLOSED_BOUNDED_OWNED_BINDING")
    validate_owned_references(storage, {ref["path"]: ref["sha256"]})
    body = private.read_local(ref["path"], cap)
    require(len(body) == ref["bytes"] and private.sha(body) == ref["sha256"], "EXACT_OWNED_INPUT_BYTES")
    return body if raw else private_json(body)


def private_json(body):
    from .gha_private_checkpoint import strict_json
    return strict_json(body)


def fresh(storage, path):
    path = private.parents_safe(path)
    require(not path.exists(), "FRESH_PHASE_ROOT_NO_RETRY")
    return storage.register_root(path)


def write(storage, path, document):
    storage.write_bytes(path, canonical(document))
    p=Path(path).absolute()
    with p.open("rb") as handle:checksum=hashlib.file_digest(handle,"sha256").hexdigest()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=checksum)


def config_check(config, slate):
    require(type(config) is dict and CONFIG_KEYS <= set(config) <= CONFIG_KEYS | {"purpose"}, "CLOSED_RUNTIME_SOURCE_CONFIG")
    purpose=config.get("purpose","SOFTWARE_ACCEPTANCE")
    require(purpose in {"SOFTWARE_ACCEPTANCE","CURRENT_OPERATIONAL_INFERENCE"},"EXPLICIT_SOURCE_READ_PURPOSE")
    years = config["history_seasons"]
    require(type(years) is list and years == sorted(set(years)) and years
        and all(type(y) is int and 2019 <= y <= slate["season"] for y in years)
        and slate["season"] in years and set(config["allowed_periods"]) == set(map(str, years)),
        "EXPLICIT_SUPPORTED_HISTORY_SEASONS")
    for year, weeks in config["allowed_periods"].items():
        require(type(weeks) is list and weeks == sorted(set(weeks))
            and all(type(w) is int and 1 <= w <= 18 and (int(year) != slate["season"] or w < slate["week"])
                and (purpose == "CURRENT_OPERATIONAL_INFERENCE" or int(year) != 2026 or w <= 5) for w in weeks),
            "EARLY_HISTORY_ONLY_NO_PROTECTED_CONFIRMATION")
    limits = config["freshness_seconds"]
    require(type(limits) is dict and set(limits) == {"schedule", "current_roster", "current_statistics", "players"}
        and all(type(v) is int and 0 < v <= 604800 for v in limits.values()), "EXPLICIT_BOUNDED_FRESHNESS_NO_RELAXATION")


def relocated_catalog(restored, aliases):
    require(restored["schema_version"] == retained.VERSION+"-restore"
        and restored["state"] == "CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE"
        and restored["model_pairs"] == len(restored["models"]) == len(aliases["models"]) == 18
        and restored["fits"] == 0 and restored["current_loader_replay"] is True
        and restored["model_artifact_durability"] is True and restored["public_release"] is False
        and aliases["schema_version"] == retained.VERSION+"-manifest-aliases"
        and aliases["current"] == restored["current"], "AUTHENTICATED_RETAINED_EFFECTIVE18_REQUIRED")
    catalog = deepcopy(restored["origin"]["replay_catalog"])
    effective.safe_replay_catalog(catalog)
    for slot, row, ref in zip(catalog["slots"], aliases["models"], restored["models"]):
        require((slot["target"], slot["family"], slot["method_id"], slot["model_sha256"], slot["procedure_version"],
            slot["transport_manifest_sha256"], slot["manifest_sha256"])
            == (row["target"], row["family"], row["method_id"], row["model_sha256"], row["procedure_version"],
                row["original_transport_manifest_sha256"], row["original_verified_reader_manifest_sha256"])
            and ref == row["current_manifest"], "COMPLETE_RETAINED_ALIAS_UNION_REQUIRED")
        slot["manifest_sha256"] = ref["sha256"]
    catalog.update(source_sha=restored["current"]["source_sha"], run_id=restored["current"]["run_id"])
    effective.safe_replay_catalog(catalog)
    return catalog


class Runtime:
    """One typed epoch/choice. External proof authentication belongs to parent."""
    def __init__(self, storage, registered, choice, retained_restore, config, *, clock=now_utc, progress=lambda: None, mae_owner=None):
        from . import operational_sources as sources
        numerical.loaded(Path(__file__).resolve().parents[1],os.environ)
        require(isinstance(storage, OperationalStorage) and type(registered) is epoch.RegisteredEpoch
            and type(choice) is epoch.EpochChoice, "EXISTING_OWNER_AND_TYPED_EPOCH_CHOICE_REQUIRED")
        self.storage, self.registered, self.choice = storage, registered, choice
        self.clock, self.progress = clock, progress
        registered.verify(clock()); choice.verify(registered, clock())
        slate, old = choice.document["slate"], registered.epoch.origin["slate"]
        mode = choice.document["mode"]
        require(mode in {"SOFTWARE_CORRECTION_CONTINUATION","ROUTINE_P2_CURRENT_EPOCH"}, "EXPLICIT_CORRECTION_OR_ROUTINE_PRODUCT")
        if mode == "SOFTWARE_CORRECTION_CONTINUATION":
            require((slate["season"],slate["week"]) == (old["season"],old["week"])
                and slate["weekly_deadline_utc"] == old["weekly_deadline_utc"]
                and slate["slate_contract"]["original_weekly_deadline_utc"] == old["weekly_deadline_utc"],
                "LATE_CORRECTION_MUST_PRESERVE_ORIGINAL_WEEK_AND_DEADLINE")
        else:
            require(slate["season"] == old["season"] and old["week"] < slate["week"]
                and utc(choice.document["choice"]["actual_frozen_at"]) < utc(slate["weekly_deadline_utc"]),
                "ROUTINE_WEEKLY_CHOICE_MUST_BE_PRIOR_AND_PREDEADLINE")
        config_check(config, choice.document["slate"])
        self.config, self.retained_ref = deepcopy(config), retained_restore
        self.restored = read_owned(storage, retained_restore)
        aliases = read_owned(storage, self.restored["relocation_catalog"])
        self.replay = relocated_catalog(self.restored, aliases)
        proofs = self.restored.get("proofs")
        require(type(proofs) is list and 1 <= len(proofs) <= 9
            and all(p["schema_version"] == "weekly-private-proof-v2.1" and p["phase"] == "restore"
                and p["run_id"] == self.restored["current"]["run_id"]
                and p["source_sha"] == self.restored["current"]["source_sha"]
                and p["exact_readback"] is p["separate_process"] is True for p in proofs),
            "PARENT_AUTHENTICATED_CURRENT_MODEL_RESTORE_PROOFS_REQUIRED")
        self.artifacts = epoch.artifact_catalog(registered.epoch, self.replay)
        self.versions = epoch.selected_versions(registered, choice, relocated_replays=(self.replay,), now=clock())
        self.records = []
        for ref, slot in zip(self.restored["models"], self.replay["slots"]):
            manifest = read_owned(storage, ref, 256 << 10)
            require((manifest["category"]["target"], manifest["method_id"], manifest["family"], manifest["procedure_version"],
                manifest["model"]["sha256"]) == (slot["target"], slot["method_id"], slot["family"],
                slot["procedure_version"], slot["model_sha256"]), "RETAINED_MANIFEST_SLOT_SOURCE_MISMATCH")
            self.records.append(dict(binding=ref, manifest=manifest))
        contracts = [r["manifest"]["source_contract"] for r in self.records]
        require(all(c == contracts[0] for c in contracts) and contracts[0]["source_policy_sha256"]
            == "e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441", "UNCHANGED_E7_SOURCE_CONTRACT")
        self.contract = contracts[0]
        self.policy = sources.load_source_policy(Path(__file__).resolve().parents[1]/"config/operational-source-policy-v2.json")
        self.code_pins = pins()
        self.recipe = dict(schema_version=VERSION+"-recipe", code_pins=self.code_pins, limits=LIMITS,
            acquisition_limits=ACQUISITION_LIMITS, epoch_sha256=registered.epoch.sha256, choice_sha256=choice.sha256,
            retained_restore=retained_restore, source_contract=self.contract, config=config,
            model_search=False, fits=0, old_procedure_losses_inherited=False,
            product_kind=choice.document["mode"], export_boundary=HANDOFF,
            numerical_runtime=dict(configuration_id="effective18-haswell-numpy-generic-v1",
                configuration_file_sha256=private.sha(private.read_local(Path(__file__).resolve().parents[1]/"config/audit-weekly-numerical-runtime-v1.json",32 << 10))))
        self._mae = None
        if mae_owner is not None:
            from .weekly_mae_display_runtime_v1 import BoundDisplay
            self._mae = BoundDisplay(self, mae_owner)

    def check(self):
        self.progress()
        self.choice.verify(self.registered, self.clock())
        require(self.clock() < min(map(utc, self.choice.document["slate"]["game_cutoffs"].values())), "INPUT_CUTOFF_ELAPSED_NO_BACKFILL")

    def prepare(self, output):
        self.check()
        output = fresh(self.storage, output)
        refs = dict(recipe=write(self.storage, output/"RUNTIME_RECIPE.json", self.recipe),
            choice=write(self.storage, output/"WEEKLY_CHOICE.json", self.choice.document),
            artifact_catalog=write(self.storage, output/"ARTIFACT_CATALOG.json", self.artifacts),
            selected_versions=write(self.storage, output/"SELECTED_VERSION_CATALOG.json", self.versions),
            relocated_replay=write(self.storage, output/"RELOCATED_REPLAY_CATALOG.json", self.replay))
        readback = epoch.owned_cas_readback(self.storage,
            {key:refs[key] for key in ("choice","selected_versions")},
            dict(choice=self.choice.document,selected_versions=self.versions),
            scope="CHOICE_AND_SELECTED_VERSIONS",written_at=self.clock(),clock=self.clock)
        completion = dict(schema_version=epoch.VERSION+"-choice-completion",choice_sha256=self.choice.sha256,
            catalog_sha256=self.versions["catalog_sha256"],selected_versions_sha256=digest(self.versions),
            persisted_completed_at=readback["readback_completed_at"],metadata_cas_readback=readback,
            qualified_artifact_restore=dict(scope="EFFECTIVE18_MODELS_ONLY",proof_sha256=digest(self.restored["proofs"]),
                replay_catalog_sha256=digest(self.replay),model_pairs=18),
            metadata_remote_durability_qualified=False,current_values_used=False)
        completion_ref = write(self.storage, output/"CHOICE_COMPLETION.json",completion)
        prepared_ref = write(self.storage, output/"PREPARED.json", dict(schema_version=VERSION+"-prepared", refs=refs,
            epoch_sha256=self.registered.epoch.sha256, choice_sha256=self.choice.sha256,
            actual_completed_at=self.clock().isoformat(), current_values_used=False, fits=0,
            choice_completion=completion_ref,metadata_remote_durability_qualified=False,public_export_authorized=False))
        if self._mae is not None:
            self._mae.prepare(output, prepared_ref)
        return prepared_ref

    def prepared(self, ref):
        value = read_owned(self.storage, ref)
        expected = dict(recipe=self.recipe, choice=self.choice.document, artifact_catalog=self.artifacts,
            selected_versions=self.versions, relocated_replay=self.replay)
        require(value["schema_version"] == VERSION+"-prepared" and value["current_values_used"] is False
            and value["epoch_sha256"] == self.registered.epoch.sha256 and value["choice_sha256"] == self.choice.sha256
            and set(value["refs"]) == set(expected), "EXACT_PREPARED_METADATA_REQUIRED")
        for key, document in expected.items():
            require(read_owned(self.storage, value["refs"][key]) == document, "PREPARED_METADATA_CHANGED")
        return value

    def acquire(self, prepared_ref, completion, historical_sources, output, *, downloader=None):
        from . import operational_sources as sources, weekly_future_inference as future
        """Fresh E7 transport only; statistics decoding stays in original filters."""
        from .operational_io import quota_downloader
        self.check(); prepared = self.prepared(prepared_ref)
        permit = epoch.authorize_capture(self.registered, self.choice, completion,
            relocated_replays=(self.replay,), clock=self.clock)
        require(read_owned(self.storage,prepared["choice_completion"]) == completion
            and utc(completion["persisted_completed_at"]) <= utc(prepared["actual_completed_at"]), "METADATA_COMPLETION_BEFORE_CAPTURE")
        output = fresh(self.storage, output)
        write(self.storage, output/"CONSUMED.json", dict(schema_version=VERSION, retries=0, actual_started_at=self.clock().isoformat()))
        started = self.clock(); raw = output/"source-cache"/"raw"
        specs = sources._names(self.config["history_seasons"])
        season = self.choice.document["slate"]["season"]
        mutable = {"schedules.csv", "players.parquet", f"stats_player_week_{season}.parquet", f"roster_weekly_{season}.parquet"}
        require(set(historical_sources) == set(specs)-mutable, "EXACT_AUTHENTICATED_HISTORICAL_E7_WHITELIST")
        try:
            for name, pair in historical_sources.items():
                require(set(pair) == {"body", "receipt"}, "CLOSED_HISTORICAL_SOURCE_PAIR")
                receipt = read_owned(self.storage, pair["receipt"], 64 << 10)
                require(receipt["url"] == specs[name]["url"] and receipt["status"] == "acquired"
                    and receipt["sha256"] == pair["body"]["sha256"] and receipt["bytes"] == pair["body"]["bytes"], "AUTHENTIC_HISTORICAL_RECEIPT")
                validate_owned_references(self.storage, {pair["body"]["path"]: pair["body"]["sha256"]})
                self.storage.import_file(pair["body"]["path"], raw/name, expected_sha256=pair["body"]["sha256"])
                self.storage.import_file(pair["receipt"]["path"], raw/(name+".receipt.json"), expected_sha256=pair["receipt"]["sha256"])
            download = downloader if downloader is not None else quota_downloader(self.storage)
            for name in sorted(mutable):
                self.check()
                require(not (raw/name).exists(), "MUTABLE_SOURCE_MUST_ACTUALLY_REFRESH")
                receipt = download(raw, name, specs[name]["url"], refresh_daily=False)
                require(receipt["status"] == "acquired" and receipt.get("cache_reused") is False
                    and not receipt.get("stale") and started <= utc(receipt["retrieved_utc"]) <= self.clock(), "NO_RELABELLED_OR_STALE_MUTABLE_SOURCE")
                self.storage.import_file(raw/name, raw/name, expected_sha256=receipt["sha256"])
                self.storage.import_file(raw/(name+".receipt.json"), raw/(name+".receipt.json"))
            total = sum((raw/name).stat().st_size for name in specs)
            require(total <= ACQUISITION_LIMITS["source_bytes"], "SOURCE_BODY_BYTE_CAP")
            asof = self.clock()
            manifest = sources.acquire_operational_history(self.storage.cache, self.config["history_seasons"], self.policy, asof,
                source_cache=raw.parent, allowed_periods=self.config["allowed_periods"], storage=self.storage)
            generic.validate_freshness(manifest["source_receipts"], now=self.clock(), season=season, limits=self.config["freshness_seconds"])
            from .weekly_source_read_batch import manifest_bindings
            request = self.storage.cache/"operational-source-v2"/self.policy["_policy_sha256"]/"requests"/(sources._digest(manifest["request"])+".json")
            bindings = manifest_bindings(manifest["namespace"], manifest, manifest_sha256=manifest["manifest_sha256"],
                request_binding=str(request), request_binding_sha256=future.sha(request))
            validate_owned_references(self.storage, bindings)
            self.check()
            result = dict(schema_version=VERSION+"-source", state="FRESH_E7_SOURCE_PREPARED", prepared=prepared_ref,
                permit=permit.document, completion=completion, actual_source_started_at=started.isoformat(),
                actual_completed_at=self.clock().isoformat(), asof_utc=asof.isoformat(), namespace=manifest["namespace"],
                manifest=manifest, bindings=bindings, raw={name:future.binding(raw/name) for name in specs},
                mutable_refreshed=sorted(mutable), source_bytes=total, fits=0, protected_confirmation_reads=0,
                historical_availability="FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION", upstream_publication="NOT_INFERRED")
            return write(self.storage, output/"SOURCE_FINISHED.json", result)
        except BaseException as error:
            write(self.storage, output/"SOURCE_FAILED.json", dict(schema_version=VERSION, state="FAILED_RETAINED",
                reason=reason(error), fits=0, successful_forecast=False, retries=0, public_export_authorized=False))
            raise

    def infer(self, prepared_ref, source_ref, output):
        from . import operational_sources as sources, weekly_future_inference as future, weekly_current_query as query
        """No network, fitting, outcome/scoring API or new family selection."""
        from . import weekly_current_inference as current
        from .weekly_source_read_batch import source_read_operation
        self.check(); prepared = self.prepared(prepared_ref)
        source = read_owned(self.storage, source_ref)
        require(source["schema_version"] == VERSION+"-source" and source["state"] == "FRESH_E7_SOURCE_PREPARED"
            and source["prepared"] == prepared_ref and source["manifest"]["request"]["allowed_periods"] == self.config["allowed_periods"], "EXACT_PREPARED_FRESH_SOURCE_REQUIRED")
        permit = epoch.authorize_capture(self.registered, self.choice, source["completion"], relocated_replays=(self.replay,),
            clock=lambda: utc(source["permit"]["actual_capture_authorized_at"]))
        require(permit.document == source["permit"] and read_owned(self.storage,prepared["choice_completion"]) == source["completion"]
            and utc(source["completion"]["persisted_completed_at"]) <= utc(prepared["actual_completed_at"])
            and utc(permit.document["actual_capture_authorized_at"]) <= utc(source["actual_source_started_at"])
            <= utc(source["actual_completed_at"]) <= self.clock(), "SOURCE_ACTUAL_CLOCKS_AND_METADATA_PERMIT")
        slate = self.choice.document["slate"]
        generic.validate_freshness(source["manifest"]["source_receipts"], now=self.clock(), season=slate["season"], limits=self.config["freshness_seconds"])
        mutable = {"schedules.csv", "players.parquet", f"stats_player_week_{slate['season']}.parquet", f"roster_weekly_{slate['season']}.parquet"}
        require(set(source["mutable_refreshed"]) == mutable and all(utc(source["actual_source_started_at"])
            <= utc(source["manifest"]["source_receipts"][name]["retrieved_utc"]) <= utc(source["actual_completed_at"])
            and source["manifest"]["source_receipts"][name].get("cache_reused") is False for name in mutable), "GENUINE_CURRENT_REFRESH_WITNESSES_REQUIRED")
        validate_owned_references(self.storage, source["bindings"])
        validate_owned_references(self.storage, {r["path"]:r["sha256"] for r in source["raw"].values()})
        output = fresh(self.storage, output)
        anchor = self.storage.snapshot()["physical_bytes"]
        class Sink(current.BoundedOutput):
            # Existing generic producer's16MiB allowance; same original sink
            # admission and twoMiB failure-control reserve, no cap change.
            def __init__(self, storage, root):
                self.storage,self.root,self.maximum,self.unpublished = storage,root,LIMITS["new_bytes"],0
        sink = Sink(self.storage, output)
        def save(name, value): return write(sink, output/name, value)
        save("CONSUMED.json", dict(schema_version=VERSION, actual_started_at=self.clock().isoformat(), retries=0))
        session = None; result = None; fatal = None
        try:
            import pandas as pd
            schedule_ref = source["raw"]["schedules.csv"]
            roster_ref = source["raw"][f"roster_weekly_{slate['season']}.parquet"]
            schedule = pd.read_csv(schedule_ref["path"], usecols=query.SCHEDULE_COLUMNS+["espn"])
            # Query construction and the exact bridge already use this same
            # canonical identity mapping. Coverage must compare that contract,
            # rather than raw nfldata LA against canonical LAR.
            for side in ("home_team","away_team"):
                schedule[side]=query.data._team(schedule[side])
            local = pd.to_datetime(schedule.gameday.astype(str)+" "+schedule.gametime.astype(str), errors="coerce")
            calendar = schedule.assign(kickoff_utc=local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC"))
            derived = generic.prepare_slate(calendar.to_dict("records"), season=slate["season"], week=slate["week"],
                game_cutoffs=slate["game_cutoffs"], now=self.clock())
            require(derived["schedule_identity_sha256"] == slate["schedule_identity_sha256"], "FRESH_SCHEDULE_CHANGED_NEW_METADATA_REQUIRED")
            roster = pd.read_parquet(roster_ref["path"], columns=query.ROSTER_COLUMNS,
                filters=[[("season", "==", slate["season"]), ("week", "==", slate["week"]), ("game_type", "==", "REG")]])
            packet = query.build_current_queries(roster, schedule, season=slate["season"], week=slate["week"],
                cutoff_utc=self.clock(), maximum_rows=1000, expected_remaining_games=len(slate["game_cutoffs"]))
            queries = packet["queries"]
            require(not queries.empty, "NO_UNAMBIGUOUS_CURRENT_OFFERS")
            expected_sides = {(g["game_id"],g[side]) for g in schedule.to_dict("records")
                if g["game_id"] in slate["game_cutoffs"] for side in ("home_team","away_team")}
            require(set(queries.game_id) == set(slate["game_cutoffs"])
                and set(zip(queries.game_id,queries.team)) == expected_sides, "ALL_FUTURE_GAME_SIDES_REQUIRE_CURRENT_ROSTER_COVERAGE")
            queries["cutoff_utc"] = queries.game_id.map(slate["game_cutoffs"]).map(utc)
            for key in ("queries", "quarantine", "no_remaining_game"):
                stream = __import__("io").BytesIO();packet[key].to_parquet(stream, index=False)
                sink.write_bytes(output/(key+".parquet"), stream.getvalue())
            qref = future.binding(output/"queries.parquet")
            bridge = generic.exact_bridge(queries, schedule, schedule_binding=schedule_ref, query_binding=qref, season=slate["season"], week=slate["week"])
            bref = save("IDENTITY_BRIDGE.json", dict(schema_version=VERSION+"-identity", identities=list(bridge.values()),
                visible_board_match="NOT_YET_CHECKED", name_matching=False))
            save("RUNTIME_RECIPE.json", self.recipe);save("WEEKLY_CHOICE.json", self.choice.document)
            save("ARTIFACT_CATALOG.json", self.artifacts);save("SELECTED_VERSION_CATALOG.json", self.versions)
            save("POPULATION.json", packet["coverage"])
            save("MODEL_ATTEMPTS.json", dict(slots=[dict(target=r["manifest"]["category"]["target"], method_id=r["manifest"]["method_id"],
                artifact=r["binding"], state="NOT_ATTEMPTED") for r in self.records], prediction_rows_cap=18000))
            with source_read_operation(self.storage, source["bindings"]):
                prior = sources.load_operational_history(self.storage.cache, self.config["history_seasons"], self.policy,
                    source["asof_utc"], allowed_periods=self.config["allowed_periods"])
            features = query.build_shared_features(prior, packet, policy=self.policy, source_contract=self.contract)
            del prior
            require(len(features)*18 <= LIMITS["prediction_rows"], "ALL18_ROW_CAP_NO_TRUNCATION")
            with generic.owned_feature_output(self.storage, sink) as owner:
                fref, cref = future.persist_feature_capture(output/"features.parquet", features,
                    features=[n for n in features if n.startswith("f_")], source_contract=self.contract,
                    source_bindings=[*source["raw"].values()], storage=owner, clock=self.clock)
            capture = read_owned(self.storage, cref)
            self.check()
            session = future.FutureInferenceSession.from_storage(self.storage)
            session.prepare([r["binding"] for r in self.records])
            statuses, all_rows = self._candidates(session, features, capture, cref, bridge, sink, output)
            candidate_ref = save("CANDIDATES.json", dict(schema_version=VERSION+"-candidates", slots=statuses,
                prediction_rows=sum(s["issued_rows"] for s in statuses), fixed_slots=18, all_offers_preserved=True))
            complete = all(s["state"] == "CAPTURED" for s in statuses)
            selected = self._selected(queries, all_rows, bridge, source, capture, prepared_ref,permit) if complete else []
            receipt = future.persist_policy_inputs(output/"selected.jsonl.gz", [selected], storage=sink,
                max_serialized_bytes=4 << 20, clock=self.clock)
            session.close();session = None
            self.check()
            require(pins() == self.code_pins and self.storage.snapshot()["physical_bytes"]-anchor <= LIMITS["new_bytes"], "RUNTIME_RECIPE_OR_OUTPUT_BUDGET_CHANGED")
            result = dict(schema_version=VERSION+"-result", state="PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE" if complete else "PARTIAL_RETAINED_NOT_QUALIFIED",
                recipe_sha256=digest(self.recipe), epoch_sha256=self.registered.epoch.sha256, choice_sha256=self.choice.sha256,
                candidates=candidate_ref, selected=receipt, bridge=bref, features=fref, feature_capture=cref,
                prepared=prepared_ref, source=source_ref, model_pairs=18, prediction_rows=len(all_rows),
                query_rows=len(queries),future_games=derived["scheduled_games"]-derived["elapsed_games"],
                elapsed_games=derived["elapsed_games"],selected_rows=len(selected),
                selected_operational_rows=sum(r["operational_eligible"] for r in selected),
                abstentions=sum(not r["operational_eligible"] for r in selected),
                fits=0, searches=0, scores=0, protected_confirmation_reads=0, HTTP=0,
                original_weekly_deadline_utc=self.registered.epoch.origin["slate"]["weekly_deadline_utc"],
                original_choice_clock=self.registered.epoch.origin["choice"]["actual_frozen_at"],
                effective_choice_clock=self.choice.document["choice"]["actual_frozen_at"], product_kind=self.choice.document["mode"],
                actual_completed_at=self.clock().isoformat(), independent_remote_restore="REQUIRED_BEFORE_PUBLIC_USE",
                successful_forecast=False, scientific_qualification=False, public_release=False, public_export_authorized=False)
        except BaseException as error:
            fatal = reason(error)
        finally:
            if session is not None:
                try: session.close()
                except BaseException: fatal = fatal or "MODEL_SESSION_CLOSE_FAILED"
        if fatal:
            result = dict(schema_version=VERSION+"-result", state="FAILED_RETAINED", reason=fatal, successful_forecast=False,
                fits=0, public_release=False, public_export_authorized=False, retries=0, actual_completed_at=self.clock().isoformat())
        ref = save("FINISHED.json", result)
        if result["state"] == "PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE":
            save("EXPORT_INPUTS.json", dict(schema_version=HANDOFF, terminal=ref, selected=receipt["binding"],
                completion=future.binding(output/"selected.jsonl.completion.json"), prepared=prepared_ref, source=source_ref,
                candidates=candidate_ref, identity_bridge=bref, recipe=future.binding(output/"RUNTIME_RECIPE.json"),
                choice=future.binding(output/"WEEKLY_CHOICE.json"), artifact_catalog=future.binding(output/"ARTIFACT_CATALOG.json"),
                selected_version_catalog=future.binding(output/"SELECTED_VERSION_CATALOG.json"),
                requires_new_epoch_checkpoint_export_consumer=True, rights=None, durability=None, public_export_authorized=False))
        # The original session, FINISHED and successful handoff are complete
        # before optional point work can register refs or consume more budget.
        if self._mae is not None and fatal is None:
            self._mae.capture(features, capture, cref, source, source_ref, prepared_ref,
                bridge, bref, sink, output, receipt, statuses)
        return ref

    def _candidates(self, session, features, capture, capture_ref, bridge, sink, output):
        from . import weekly_future_inference as future
        from .weekly_current_inference import projection_receipts
        records = [dict(r, eligible_roles=sorted(set(features.position))) for r in self.records]
        groups = []
        for ordinal, (cutoff, frame) in enumerate(features.groupby("cutoff_utc", sort=False)):
            views, keys = projection_receipts(records, frame, capture, capture_ref, storage=sink, output=output/f"views/{ordinal}", clock=self.clock)
            groups.append((cutoff, views, keys))
        statuses, all_rows = [], []
        for record in records:
            m, ref = record["manifest"], record["binding"]
            rows, failure = [], None
            try:
                for cutoff, views, keys in groups:
                    view = views[keys[ref["sha256"]]]
                    identities = {(q["season"],q["week"],q["game_id"],q["player_id"]):q
                        for q in view["view"][["season","week","game_id","player_id","position","cutoff_utc","kickoff_utc"]].to_dict("records")}
                    for chunk in session.predict_chunks(ref["sha256"], view["view"], context=dict(
                        cutoff_utc=utc(cutoff).isoformat(), weekly_decision_cutoff_utc=self.choice.document["choice"]["actual_frozen_at"],
                        slate_id=self.choice.document["slate"]["slate_id"], source_contract=self.contract, evidence_lane="original_pregame",
                        reference_stream="candidate", query_source_sha256=capture["feature_binding"]["sha256"], feature_capture_receipt=view["binding"]),
                        clock=self.clock, batch_size=128):
                        self.check()
                        for row in chunk:
                            require(set(row) == BASE_CANDIDATE_KEYS and len(rows) < 1000 and row["method_id"] == m["method_id"] and row["category"] == m["category"]["target"]
                                and row["model_version"] == ref["sha256"] and row["procedure_version"] == m["procedure_version"], "EXACT_CANDIDATE_SLOT_FIELDS")
                            key = (row["season"], row["week"], row["game_id"], row["player_id"])
                            value = row["forecast_value"]
                            require(key in bridge and (value is None or type(value) in (int,float) and math.isfinite(value)), "FINITE_CANDIDATE_VALUE_OR_UNAVAILABLE")
                            require((row["product"],row["prediction_functional"],row["metric"]) == future.product(m["category"])
                                and (value is None or m["category"]["support"] != "count" or value >= 0)
                                and (value is None or m["category"]["support"] != "bernoulli" or 0 <= value <= 1)
                                and row["training_cutoff_utc"] == m["training_cutoff_utc"]
                                and row["training_max_available_utc"] == m["training_max_available_utc"]
                                and all(row[k] == m["fit_receipt"][k] for k in ("training_started_at","training_completed_at","training_source_capture_completed_at")),
                                "CANDIDATE_PRODUCT_SUPPORT_OR_ORIGINAL_FIT_PROVENANCE_CHANGED")
                            require(key in identities, "CANDIDATE_OUTSIDE_ORIGINAL_CURRENT_COHORT")
                            expected = identities[key]
                            require(row["offered_id"] == digest(dict(season=key[0],week=key[1],game_id=key[2],player_id=key[3],category=m["category"]["target"]))
                                and all(utc(row[k]) == utc(expected[k]) for k in ("cutoff_utc","kickoff_utc"))
                                and row["position"] == expected["position"] and row["source_policy_sha256"] == self.contract["source_policy_sha256"]
                                and row["artifact_sha256"] == ref["sha256"] and row["evidence_lane"] == "original_pregame"
                                and row["reference_stream"] == "candidate" and row["operational_eligible"] is (value is not None)
                                and row["horizon"] == "player_game" and row["slate_id"] == self.choice.document["slate"]["slate_id"]
                                and row["weekly_decision_cutoff_utc"] == self.choice.document["choice"]["actual_frozen_at"]
                                and row["source_capture_completed_at"] == capture["feature_persist_completed_at"]
                                and row["scientific_qualification"] is False
                                and utc(view["ready_at"]) <= utc(row["issued_at"]) < utc(row["cutoff_utc"]), "CANDIDATE_IDENTITY_CLOCK_OR_ELIGIBILITY_CHANGED")
                            row.update(bridge[key], runtime_recipe_sha256=digest(self.recipe), correction_epoch_sha256=self.registered.epoch.sha256,
                                source_cutoff_utc=row["cutoff_utc"], participation_state="unknown", capture_registration_id=VERSION,
                                source_projection_receipt=view["binding"], source_projection_receipt_completed_at=view["ready_at"],
                                original_choice_clock=self.registered.epoch.origin["choice"]["actual_frozen_at"],
                                original_weekly_deadline_utc=self.registered.epoch.origin["slate"]["weekly_deadline_utc"],
                                product_kind=self.choice.document["mode"], attempt_qualified=True, public_export_authorized=False,
                                primary_role=row["position"] in m["category"]["primary_roles"],
                                modeled_role=row["position"] in m["category"]["modeled_roles"])
                            if not row["modeled_role"]:
                                row.update(operational_eligible=False,role_qualification="OUTSIDE_REGISTERED_MODELED_ROLES_PRIVATE_ONLY")
                            rows.append(row)
                require(len(rows) == len(features) and len({r["offered_id"] for r in rows}) == len(features), "COMPLETE_SLOT_ALL_CURRENT_IDENTITIES_REQUIRED")
            except Exception as error:
                failure = reason(error)
                for row in rows: row.update(operational_eligible=False, attempt_qualified=False)
            receipt = future.persist_policy_inputs(output/"candidates"/m["category"]["target"]/(m["method_id"]+".jsonl.gz"), [rows],
                storage=sink, max_serialized_bytes=4 << 20, clock=self.clock)
            expected = [digest({**{k:r[k] for k in ("season", "week", "game_id", "player_id")}, "category":m["category"]["target"]}) for r in features.to_dict("records")]
            observed = {r["offered_id"] for r in rows}
            status = dict(target=m["category"]["target"], method_id=m["method_id"], artifact=ref,
                state="CAPTURED" if failure is None else "FAILED_RETAINED", failure=failure, persistence=receipt,
                expected_rows=len(expected), issued_rows=len(rows), unissued_offered_ids=[i for i in expected if i not in observed],
                attempt_qualified=failure is None)
            write(sink, output/"model-status"/(m["category"]["target"]+"-"+m["method_id"]+".json"), status)
            statuses.append(status);all_rows.extend(rows)
        return statuses, all_rows

    def _selected(self, queries, rows, bridge, source, capture, prepared_ref,permit):
        slate = self.choice.document["slate"]
        offers = generic.offers(queries, self.records, slate)
        ids = {o["offered_id"] for o in offers}
        panel = selector.Panel(dict(schema_version=selector.VERSION, offers=offers, forecasts=[r for r in rows if r["offered_id"] in ids],
            outcomes=[], decisions=[s["decision"] for s in self.choice.document["choice"]["selections"]], weeks=[]), self.artifacts["catalog"])
        allowed = {(r["category"], r["procedure_version"], r["model_version"]) for r in self.versions["rows"]}
        output = []
        for selection in self.choice.document["choice"]["selections"]:
            procedure = digest(dict(schema_version=epoch.VERSION+"-issued-procedure", epoch_sha256=self.registered.epoch.sha256,
                selection_recipe_sha256=digest(self.registered.epoch.document["selection_recipe"]), category=selection["decision"]["category"], members=selection["members"]))
            for row in generic.issue_registered(selector, panel, selection, atomic_TD=True):
                self.check(); issued = self.clock()
                require(len(output) < LIMITS["selected_rows"], "SELECTED_ROW_CAP_NO_TRUNCATION")
                epoch.validate_materialization(permit, source_started_at=source["actual_source_started_at"],
                    source_completed_at=source["actual_completed_at"], issued_at=issued, game_id=row["game_id"])
                version = digest([(c["method_id"], c["model_version"], c["weight"]) for c in row["components"]])
                require(row["forecast_value"] is None or (row["category"], procedure, version) in allowed, "PREREGISTERED_SELECTED_VERSION_REQUIRED")
                require(all(utc(c["provenance"]["issued_at"]) <= issued for c in row["components"]), "SELECTED_CLOCK_BEFORE_COMPONENT")
                row.update(bridge[(row["season"],row["week"],row["game_id"],row["player_id"])], issued_at=issued.isoformat(),
                    method_id="P2_SELECTED", procedure_version=procedure, model_version=version, decision_binding=prepared_ref,
                    runtime_recipe_sha256=digest(self.recipe), correction_epoch_sha256=self.registered.epoch.sha256,
                    source_capture_completed_at=capture["feature_persist_completed_at"], source_policy_sha256=self.contract["source_policy_sha256"],
                    source_cutoff_utc=row["cutoff_utc"], operational_eligible=row["forecast_value"] is not None,
                    original_choice_clock=self.registered.epoch.origin["choice"]["actual_frozen_at"],
                    original_weekly_deadline_utc=self.registered.epoch.origin["slate"]["weekly_deadline_utc"], product_kind=self.choice.document["mode"],
                    scientific_qualification=False, public_export_authorized=False, publication_status="PRIVATE_PENDING_DURABLE_FRESH_READER")
                output.append(row)
        require(output, "NO_SELECTED_CURRENT_OPPORTUNITIES")
        return output
