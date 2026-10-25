"""Read-only, TLS-verified qualification of the exact public COUNT7 delivery.

Only public source/derived forecasts and closed execution metadata are read.
No private capture, provider outcome, credential or model is opened.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zlib

BASE = Path('/workspace/nfl-system-audit/continuation')
PREVIEW = BASE / 'count-release-packet-current-7/preview'
sys.path.insert(0, str(PREVIEW / 'tools'))
import weekly_public_feed as wire
import weekly_public_feed_v4 as consumer

SOURCE = 'c74812b441c15d8e45daa09021f428ed131ff7cf'
FEED_SHA = '214b3983f6fc6cbf2907afa1ef4ae0bd002179fdf99c78b9bc739b1f8431dd4c'
RECEIPT_SHA = 'ab065477019becb3546da50169341b4d884dd9d9976cb4ce3e32ed7bbb9abec0'
RUN = '40203512153'
ROOT = 'https://raw.githubusercontent.com/NickNicky19/NFL-forecasting/lab-state/state/'
FEED_PATH = 'public/weekly-adaptive-v1/2026-W07/20261025T145527.113720Z--' + FEED_SHA + '.json'
RECEIPT_PATH = 'public/weekly-adaptive-v1/receipts/' + FEED_SHA + '.json.gz'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('REDIRECT_FORBIDDEN')

opener = build_opener(NoRedirect())
responses = []
def fetch(url, cap):
    assert url.startswith(('https://raw.githubusercontent.com/NickNicky19/NFL-forecasting/',
                           'https://api.github.com/repos/NickNicky19/NFL-forecasting/'))
    request = Request(url, headers={'User-Agent': 'NFL-public-correctness-audit', 'Cache-Control': 'no-cache'})
    with opener.open(request, timeout=20) as response:
        assert response.status == 200 and response.url == url
        body = response.read(cap + 1)
        assert 0 < len(body) <= cap
    responses.append(dict(url=url, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
    return body

out = BASE / 'count7-public-verification-20261025T1522Z'
out.mkdir(exist_ok=False)
policy_body = (PREVIEW / 'config/weekly-derived-selected-policy-v4.json').read_bytes()
policy = wire.strict_public_json(policy_body)
consumer.policy_check(policy, root=PREVIEW, now=datetime.now(timezone.utc).isoformat())
body = fetch(ROOT + FEED_PATH, 4 << 20)
assert hashlib.sha256(body).hexdigest() == FEED_SHA
feed = wire.strict_public_json(body)
assert body == wire.canonical(feed)
assert feed['publication']['source_sha'] == SOURCE and feed['publication']['run_id'] == RUN
raw = fetch(ROOT + RECEIPT_PATH, 64 << 10)
assert hashlib.sha256(raw).hexdigest() == RECEIPT_SHA
decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
plain = decoder.decompress(raw, (64 << 10) + 1)
assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(plain) <= 64 << 10
receipt = wire.strict_public_json(plain)
assert plain == wire.canonical(receipt) and set(receipt) == consumer.RECEIPT_KEYS
assert receipt['feed_sha256'] == FEED_SHA and receipt['feed_bytes'] == len(body)
assert receipt['rows'] == len(feed['rows']) and receipt['fits'] == 0 and receipt['raw_or_models_public'] is False
assert receipt['root_go_sha256'] == 'c7f1119e48d55e4253c1faf86b810e949d69e910f23ac7ad719449577ebdd84f'
assert receipt['policy_sha256'] == '8cf0df7f10842639f814daedb82231064fab0c4816cb4740bcc13c9263a06791'
assert receipt['source_sha'] == SOURCE and receipt['run_id'] == RUN
categories = sorted({r['category'] for r in feed['rows']})
assert categories == sorted(consumer.old.overlay().PRODUCTS) == receipt['categories']
assert set(receipt['jobs']) == {'produce', 'restore', 'consume'}
assert {k:v['api_job_id'] for k,v in receipt['jobs'].items()} == {
    'produce':121199486624, 'restore':121201823053, 'consume':121202129920}
proof = consumer.verify_execution(feed, policy, now=datetime.now(timezone.utc).isoformat(), fetch=fetch)
summary = dict(schema_version='count7-independent-public-verification-v1',
    state='PASS_PUBLIC_DELIVERY_NOT_WEBSITE_INSTALLATION', observed_at=datetime.now(timezone.utc).isoformat(),
    tls_verified=True, redirects=False, source_sha=SOURCE, run_id=RUN,
    feed_sha256=FEED_SHA, feed_bytes=len(body), rows=len(feed['rows']), categories=categories,
    receipt_sha256=RECEIPT_SHA, receipt_plain_sha256=hashlib.sha256(plain).hexdigest(),
    public_policy_sha256=receipt['policy_sha256'], website_policy_file_sha256=hashlib.sha256(policy_body).hexdigest(),
    jobs=receipt['jobs'], fits=0, protected_outcomes_read=False, private_models_read=False,
    website_installed=False, source_bound_consumer_proof=proof, responses=responses,
    limitation='Public evidence is not an independent reproduction of private forecast accuracy; actual website combined CI, deployment and live consumption remain required.')
(out / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
(out / 'PUBLIC-receipt.json.gz').write_bytes(raw)
print(json.dumps({k:summary[k] for k in ('state','source_sha','run_id','feed_sha256','rows','categories','receipt_sha256','jobs','website_installed')}))
