"""Lossless, hash-bound storage for public aggregate registry documents.

The canonical JSON entry point stays discoverable. Large documents may bind a
gzip member in the SAME accounted directory. No record is removed or rewritten;
the decompressed bytes, counts and checksums must match before use.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path

ENCODING = 'opportunity-public-aggregate-gzip-v1'
MAX_COMPRESSED = 2 * 1024**2
MAX_UNCOMPRESSED = 4 * 1024**2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_document(path):
    path = Path(path)
    doc = json.loads(path.read_bytes())
    if doc.get('storage_encoding') != ENCODING:
        return doc
    ref = doc['content_reference']
    name = ref['file']
    if (not isinstance(name, str) or Path(name).name != name or
            not name.endswith('.json.gz')):
        raise ValueError('same-directory gzip registry member required')
    member = path.parent / name
    if member.is_symlink() or not member.is_file():
        raise ValueError('regular registry payload required')
    if not 0 < ref['bytes'] <= MAX_COMPRESSED or member.stat().st_size != ref['bytes']:
        raise ValueError('registry compressed byte count mismatch')
    compressed = member.read_bytes()
    if digest(compressed) != ref['sha256']:
        raise ValueError('registry compressed checksum mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as reader:
        raw = reader.read(MAX_UNCOMPRESSED + 1)
    if len(raw) > MAX_UNCOMPRESSED or len(raw) != ref['uncompressed_bytes']:
        raise ValueError('registry expanded byte count mismatch')
    if digest(raw) != ref['uncompressed_sha256']:
        raise ValueError('registry expanded checksum mismatch')
    result = json.loads(raw)
    if result.get('storage_encoding') == ENCODING:
        raise ValueError('nested registry encodings forbidden')
    collection = doc.get('collection_key', 'records')
    if collection not in {'records', 'panels'} or not isinstance(result.get(collection), list):
        raise ValueError('explicit supported aggregate collection required')
    if len(result[collection]) != doc['record_count']:
        raise ValueError('registry record count mismatch')
    return result


def write_document(path, document, *, compress=False, collection_key='records'):
    path = Path(path)
    previous = json.loads(path.read_bytes()) if path.exists() else {}
    raw = (json.dumps(document, indent=2, allow_nan=False) + '\n').encode()
    if not compress and previous.get('storage_encoding') != ENCODING:
        path.write_bytes(raw)
        return None
    return pack_bytes(path, raw, collection_key=collection_key)


def pack_bytes(path, raw, *, collection_key='records'):
    """Preserve original JSON bytes exactly, including numeric precision."""
    path = Path(path)
    document = json.loads(raw)
    if collection_key not in {'records', 'panels'} or not isinstance(document.get(collection_key), list):
        raise ValueError('explicit supported aggregate collection required')
    if len(raw) > MAX_UNCOMPRESSED or document.get('storage_encoding') == ENCODING:
        raise ValueError('bounded original aggregate document required')
    compressed = gzip.compress(raw, mtime=0)
    if len(compressed) > MAX_COMPRESSED:
        raise ValueError('bounded compressed aggregate document required')
    member = path.with_name(path.stem + '.' + digest(compressed) + '.json.gz')
    if member.exists() and member.read_bytes() != compressed:
        raise ValueError('immutable aggregate member conflict')
    member.write_bytes(compressed)
    ref = {'file': member.name, 'bytes': len(compressed), 'sha256': digest(compressed),
           'uncompressed_bytes': len(raw), 'uncompressed_sha256': digest(raw)}
    index = {'storage_encoding': ENCODING, 'record_count': len(document[collection_key]),
             'content_reference': ref,
             'reader': 'nfl_lab.opportunity_registry_storage_v1.read_document',
             'scope': 'Lossless public aggregate storage only; no forecast or score change.'}
    if collection_key != 'records':
        index['collection_key'] = collection_key
    path.write_text(json.dumps(index, indent=2) + '\n')
    if read_document(path) != document:
        raise ValueError('aggregate semantic readback mismatch')
    return ref
