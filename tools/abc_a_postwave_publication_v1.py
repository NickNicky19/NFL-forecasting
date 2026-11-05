"""Explicit public-safe post-wave Git payload; no remote or private-store writes."""
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'reports/abc-championship/post-wave-5w-v1'
SOURCES = [
    'nfl_lab/abc_conditional_carry_v1.py',
    'nfl_lab/count_a_mean_export_adapter_v1.py',
    'nfl_lab/product_test_week_floor_v1.py',
    'tools/abc_a_postwave_component_audit_v1.py',
    'tools/abc_a_postwave_conditional_carry_v1.py',
    'tools/abc_a_count_a_restore_and_parity_v3.py',
    'tools/abc_a_five_week_qualification_v4.py',
    'tools/abc_a_probability_floor_supplement_v1.py',
    'tools/abc_a_postwave_software_checks_v1.py',
    'tools/abc_a_postwave_records_v1.py',
    'tools/abc_a_postwave_delivery_package_v1.py',
    'tools/abc_a_postwave_publication_v1.py',
    'tools/abc_a_postwave_metadata_amendment_v1.py',
]
CANONICAL = [
    'METHOD_REGISTRY.json', 'EXPERIMENT_REGISTRY.json', 'ALL_RESULTS.json',
    'PUBLICATION_RECORDS.json', 'FOUR_CATEGORY_LEADERBOARD.json', 'RUN_EVENTS.jsonl',
    'TASK_LEDGER.jsonl', 'SOFTWARE_TESTS.json', 'SCOPE.md', 'README.md',
]
BAD = re.compile(r'[/]workspace/|[/]tmp/|[/]home/runner/|s3[:]//|sediment[:]//|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{16,}|"player_id"\s*:\s*"00-')


def build():
    new = {p for p in (ROOT / PREFIX).rglob('*') if p.is_file()}
    new.update(ROOT / p for p in SOURCES)
    if sum(p.stat().st_size for p in new) > 1048576:
        raise ValueError('postwave new public metadata exceeds registered 1MiB allocation')
    paths = set(new)
    paths.update(ROOT / 'reports/opportunity-four' / p for p in CANONICAL)
    index = json.loads((ROOT / 'reports/opportunity-four/ALL_RESULTS.json').read_bytes())
    paths.add(ROOT / 'reports/opportunity-four' / index['content_reference']['file'])
    paths.update(ROOT / p for p in ['reports/abc-championship/README.md', 'reports/abc-championship/EXPORT_INDEX.json'])
    payload = {}
    for path in sorted(paths):
        if path.is_symlink() or path.suffix not in {'.py', '.json', '.jsonl', '.gz', '.md', '.txt', '.csv'}:
            raise ValueError('noncanonical or unsupported public file')
        raw = path.read_bytes()
        text = gzip.decompress(raw).decode() if raw[:2] == b'\x1f\x8b' else raw.decode()
        if BAD.search(text):
            raise ValueError('restricted locator/row/secret pattern in ' + str(path.relative_to(ROOT)))
        if path.suffix in {'.json', '.jsonl', '.gz'}:
            for item in text.splitlines() if path.suffix == '.jsonl' else [text]:
                json.loads(item, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        payload[str(path.relative_to(ROOT))] = raw
    return payload


def main():
    p = build()
    print(json.dumps({'files': [{'path': n, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
                                 'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()} for n, b in p.items()],
                      'total_bytes': sum(map(len, p.values())), 'new_wave_bytes': sum(len(b) for n,b in p.items() if n.startswith(PREFIX) or n in SOURCES)}))


if __name__ == '__main__':
    main()
