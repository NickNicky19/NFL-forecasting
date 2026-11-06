"""Bounded readback of two immutable published qualification aggregates."""
from pathlib import Path
import datetime
import hashlib
import json
import struct
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/execution-closure-02'
CACHE = Path('/tmp') / 'abc-execution-closure02-public'
SOURCES = [
    ('C_qualification', 'NickNicky19/NFL-forecasting-NGS-C',
     'df02c7656dd616224057176d057e2494d51c5b32',
     'reports/post-wave-5w-v1/QUALIFICATION_TABLE.json.gz',
     'bb74c007300591bb183add2e3770f57b9d65fbd5',
     'b993b2b3dd56c163db08d1c47d079b835bc5d0e52ac9f3cfb9df1510fa07ee17'),
    ('B_qualification', 'NickNicky19/NFL-forecasting-V2',
     'b23349ca723868e8bb79ff4a581125c20919e756',
     'reports/post-wave-5w-v1/B-product-week-qualification-v3/B_PRODUCT_WEEK_QUALIFICATION.json.gz',
     'd94083494215f2acebd9623c300b3bff6e86201d', None),
]


def main():
    CACHE.mkdir(exist_ok=True)
    records = []
    total = 0
    for name, repo, ref, path, blob, expected in SOURCES:
        url = 'https://raw.githubusercontent.com/' + repo + '/' + ref + '/' + path
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(4194305)
        if not 0 < len(data) <= 4194304:
            raise ValueError('source exceeds registered cap')
        digest = hashlib.sha256(data).hexdigest()
        gitsha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if gitsha != blob or (expected is not None and digest != expected):
            raise ValueError('immutable source hash differs')
        total += len(data)
        if total > 8388608:
            raise ValueError('scratch cap exceeded')
        (CACHE / (name + '.json.gz')).write_bytes(data)
        records.append({'id': name, 'repository': repo, 'commit': ref, 'path': path,
                        'bytes': len(data), 'sha256': digest, 'git_blob_sha1': gitsha,
                        'gzip_expected_expanded_bytes': struct.unpack('<I', data[-4:])[0],
                        'readback': 'PASS_FULL_IMMUTABLE_PUBLIC_BYTES',
                        'rights': 'Published safe qualification metadata; private source/model/prediction rows not fetched.'})
    (CACHE / 'source_manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    result = {'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'records': records, 'compressed_scratch_bytes': total,
              'new_NFL_fits_forecasts_scoring': 0}
    (OUT / 'PUBLISHED_SOURCE_READBACK_V1.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
