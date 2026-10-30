"""One exact, public, read-only served-payload audit; no producer or source feed."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import time
import urllib.request


def main():
    folder = Path(__file__).resolve().parents[1]/'reports/category-topfive-mae-release-priority-20261030'
    plan = json.loads((folder/'CURRENT_SERVED_AUDIT_PROTOCOL_V2.json').read_bytes())
    output = folder/'CURRENT_SERVED_AUDIT_V2.json'
    assert not output.exists(), 'one actual audit per registered version'
    started = time.monotonic()
    try:
        with urllib.request.urlopen(plan['source_url'], timeout=15) as response:
            body = response.read(plan['budget']['body_cap'] + 1)
        assert len(body) == plan['expected_bytes'] and hashlib.sha256(body).hexdigest() == plan['expected_sha256']
        doc = json.loads(body)
        groups = collections.defaultdict(list)
        for row in doc['rows']:
            groups[row['category']].append(row)
        result = {'version': plan['version'], 'state': 'READ_ONLY_SERVED_PAYLOAD_AUTHENTICATED',
                  'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'payload_sha256': plan['expected_sha256'], 'payload_bytes': len(body),
                  'header': {k: doc.get(k) for k in ['schema_version', 'state', 'season', 'week', 'prepared_at', 'packaged_at', 'website_source_sha', 'publication_review_sha256']},
                  'fallback_counts': doc.get('fallback_counts'), 'categories': [], 'rows': len(doc['rows']),
                  'new_forecasts_capture_deployment_by_this_job': 0,
                  'limitation': 'A new build is not new inference; exact original row clocks and product identities are reported.'}
        for category, rows in sorted(groups.items()):
            result['categories'].append({'category': category, 'selected_rows': len(rows),
                'method_ids': sorted({r['method_id'] for r in rows}),
                'model_versions': sorted({r['model_version'] for r in rows}),
                'procedure_versions': sorted({r['procedure_version'] for r in rows}),
                'product_functionals': sorted({(r['product'], r['prediction_functional']) for r in rows}),
                'issue_times': sorted({r['issued_at'] for r in rows}),
                'source_cutoffs': sorted({r['source_cutoff_utc'] for r in rows}),
                'typed_MAE_rows': sum(r.get('selection_product') == 'stat_point_mae_v2' for r in rows),
                'separate_expected_mean_rows': sum('expected_mean' in r or 'separate_expected_mean' in r for r in rows)})
        result['wall_seconds'] = time.monotonic() - started
        encoded = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
        assert len(encoded) <= plan['budget']['retained_public_aggregate_bytes']
        output.write_bytes(encoded)
        print(json.dumps(result, indent=2))
    except BaseException as exc:
        failed = {'version': plan['version'], 'state': 'FAILED_RETAINED',
                  'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'error_type': type(exc).__name__, 'error': str(exc),
                  'HTTP_attempts': 1, 'wall_seconds': time.monotonic() - started,
                  'new_fits_models_capture_deployments': 0}
        (folder/'CURRENT_SERVED_AUDIT_FAILURE_V2.json').write_text(json.dumps(failed, indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
