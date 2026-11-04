"""Build explicit public-safe Git payloads for A's completed carry wave.

Does not touch Git refs, production, private storage or model outputs.
"""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'reports/abc-championship/predictive-improvement-01'
BAD = re.compile(r'[/]workspace/|[/]tmp/|[/]home/runner/|s3[:]//|sediment[:]//|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{16,}|"player_id"\s*:\s*"00-')
SOURCES = [
    'nfl_lab/abc_dynamic_carry_v1.py',
    'nfl_lab/category_topfive_backfield_v1.py',
    'nfl_lab/category_topfive_opportunity_registry.py',
    'nfl_lab/opportunity_registry_storage_v1.py',
    'tools/abc_a_dynamic_carry_wave_v1.py',
    'tools/abc_a_dynamic_carry_runtime_v2.py',
    'tools/abc_a_dynamic_carry_complete_v3.py',
    'tools/abc_a_dynamic_carry_analysis_v1.py',
    'tools/abc_a_dynamic_carry_supplement_v1.py',
    'tools/abc_a_dynamic_carry_records_v1.py',
    'tools/abc_a_dynamic_carry_report_v1.py',
    'tools/abc_a_carry_population_reconciliation_v1.py',
    'tools/abc_a_carry_full_board_v1.py',
    'tools/abc_a_carry_full_scorecard_export_v1.py',
    'tools/abc_a_carry_full_board_uncertainty_v1.py',
    'tools/abc_a_independent_full_board_verification_v1.py',
    'tools/abc_a_readable_wave_checkpoint_v1.py',
    'tools/verify_opportunity_registry_storage_v1.py',
    'tools/abc_a_predictive_publication_v1.py',
]
CANONICAL = [
    'METHOD_REGISTRY.json', 'EXPERIMENT_REGISTRY.json', 'ALL_RESULTS.json',
    'ABC_DYNAMIC_CARRY_SELECTION_RESULTS_V1.json', 'PUBLICATION_RECORDS.json',
    'FOUR_CATEGORY_LEADERBOARD.json', 'RUN_EVENTS.jsonl', 'TASK_LEDGER.jsonl',
    'SOFTWARE_TESTS.json', 'SCOPE.md', 'README.md',
]


def build():
    private_planning = {'PROTOCOL_PREREVIEW_DRAFT.json', 'PREFLIGHT_EXECUTION_PROTOCOL.json'}
    paths = {p for p in (ROOT / PREFIX).rglob('*') if p.is_file() and p.name not in private_planning}
    paths.update(ROOT / n for n in SOURCES)
    paths.update(ROOT / 'reports/opportunity-four' / n for n in CANONICAL)
    for n in ('ALL_RESULTS.json', 'ABC_DYNAMIC_CARRY_SELECTION_RESULTS_V1.json'):
        index = json.loads((ROOT / 'reports/opportunity-four' / n).read_bytes())
        paths.add(ROOT / 'reports/opportunity-four' / index['content_reference']['file'])
    paths.update(ROOT / n for n in ['reports/abc-championship/README.md',
                                  'reports/abc-championship/EXPORT_INDEX.json'])
    payload = {}
    for path in sorted(paths):
        if path.suffix not in {'.py', '.json', '.jsonl', '.md', '.txt', '.csv', '.gz'}:
            raise ValueError('unexpected publication file type: ' + path.name)
        raw = path.read_bytes()
        text = gzip.decompress(raw).decode() if raw[:2] == b'\x1f\x8b' else raw.decode()
        # Preserve executed source hashes. This literal is a cache of C's
        # publicly published scorer code, never an NFL/private-storage member.
        scorer_cache_sources = {
            'tools/abc_a_dynamic_carry_wave_v1.py',
            'tools/abc_a_dynamic_carry_analysis_v1.py',
            'tools/abc_a_carry_population_reconciliation_v1.py',
            'tools/abc_a_carry_full_board_v1.py',
        }
        scan_text = text
        if str(path.relative_to(ROOT)) in scorer_cache_sources:
            scan_text = text.replace('/' + 'tmp/abc-improvement-01/C/src', 'PUBLIC_C_SCORER_CODE_CACHE')
        if BAD.search(scan_text):
            raise ValueError('restricted locator/row/secret pattern in ' + str(path.relative_to(ROOT)))
        if path.suffix in {'.json', '.jsonl', '.gz'}:
            for line in text.splitlines() if path.suffix == '.jsonl' else [text]:
                json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite public JSON')))
        payload[str(path.relative_to(ROOT))] = raw
    if sum(map(len, payload.values())) > 3 * 1024**2:
        raise ValueError('finite publication metadata budget exceeded')
    return payload


def main():
    payload = build()
    out = []
    for name, raw in payload.items():
        out.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
    print(json.dumps({'files': out, 'bytes': sum(map(len, payload.values()))}))


if __name__ == '__main__':
    main()
