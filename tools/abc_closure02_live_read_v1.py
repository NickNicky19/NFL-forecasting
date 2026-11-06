"""Read existing original-site public payloads; never infer or publish forecasts."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/execution-closure-02'


def main():
    started = time.monotonic()
    cpu = time.process_time()
    records = []
    for name in ['meta', 'week']:
        url = 'https://nicknicky19.github.io/nicks-expert-nfl-picks/data/' + name + '.json'
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                raw = response.read(4194305)
                received = datetime.datetime.now(datetime.timezone.utc)
            if len(raw) > 4194304:
                raise ValueError('bounded public read exceeded4MiB')
            obj = json.loads(raw)
            record = {'public_url': url, 'status': 'READ', 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                'at_UTC': received.isoformat(), 'at_America_Chicago': received.astimezone(ZoneInfo('America/Chicago')).isoformat(),
                'keys': list(obj) if isinstance(obj, dict) else None}
            if name == 'meta':
                record['metadata'] = obj
            else:
                # Only safe schema/count metadata enters the public receipt.
                record['list_census'] = {key: len(value) for key, value in obj.items() if isinstance(value, list)}
                record['scalar_metadata'] = {key: value for key, value in obj.items()
                    if isinstance(value, (int, float, str, bool)) or value is None}
                record['container_fields'] = {key: list(value)[:25] for key, value in obj.items() if isinstance(value, dict)}
                for key, value in obj.items():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        record[key + '_row_keys'] = list(value[0])
                # No raw source, player prediction rows or private transport.
            records.append(record)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as error:
            records.append({'public_url': url, 'status': 'UNAVAILABLE',
                'error_type': type(error).__name__, 'error_sha256': hashlib.sha256(str(error).encode()).hexdigest()})
    result = {'state': 'READ_ONLY_SERVED_PAYLOAD_OBSERVATION', 'records': records,
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started,
        'new_model_inference_capture_publication': 0,
        'browser_consumption': 'NOT_VERIFIED; installed Playwright has no installed Chromium binary; no browser installed or production change.',
        'limits': 'HTTP payload readback is not rendered values, sorting, source-label or Top Picks consumer verification.'}
    with (OUT / 'LIVE_PUBLIC_READBACK_V1.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
