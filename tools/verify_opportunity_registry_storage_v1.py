"""Bounded software checks of aggregate storage; zero NFL observations or fits."""
import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab.opportunity_registry_storage_v1 import pack_bytes, read_document


def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix='aggregate-storage-check-') as d:
        p = Path(d) / 'INDEX.json'
        original = b'{"records":[{"id":"loss","score":null,"reason":"missing"},{"id":"win","score":0.12345678901234568}]}\n'
        ref = pack_bytes(p, original)
        assert read_document(p) == json.loads(original)
        checks.append('exact original byte/hash and null/precision roundtrip')
        index = json.loads(p.read_bytes())
        changes = [
            ('compressed hash mismatch', ('content_reference', 'sha256'), '0' * 64),
            ('expanded hash mismatch', ('content_reference', 'uncompressed_sha256'), '0' * 64),
            ('expanded size mismatch', ('content_reference', 'uncompressed_bytes'), len(original) + 1),
            ('record count mismatch', ('record_count',), 99),
            ('parent path rejected', ('content_reference', 'file'), '../elsewhere.json.gz'),
        ]
        for label, keys, value in changes:
            bad = copy.deepcopy(index)
            cursor = bad
            for key in keys[:-1]:
                cursor = cursor[key]
            cursor[keys[-1]] = value
            p.write_text(json.dumps(bad))
            try:
                read_document(p)
            except ValueError:
                checks.append(label)
            else:
                raise AssertionError(label)
        p.write_text(json.dumps(index))
        assert read_document(p) == json.loads(original)
        panel = Path(d) / 'LEADERBOARD.json'
        panel_raw = b'{"panels":[{"loss":0.12345678901234568,"reason":null}]}\n'
        pack_bytes(panel, panel_raw, collection_key='panels')
        assert read_document(panel) == json.loads(panel_raw)
        checks.append('explicit panels collection exact precision/null roundtrip')
        bad = json.loads(panel.read_bytes())
        bad['collection_key'] = 'unregistered_collection'
        panel.write_text(json.dumps(bad))
        try:
            read_document(panel)
        except ValueError:
            checks.append('unsupported collection rejected')
        else:
            raise AssertionError('unsupported collection rejected')
    print(json.dumps({'state': 'PASS', 'software_checks': checks,
                      'new_fits_inference_forecasts_scored_NFL_rows': 0}))


if __name__ == '__main__':
    main()
