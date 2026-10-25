"""Compare the current public producer feed to the deployed consumer graph.

Only hashes, category totals and checks are emitted; no forecast rows exported.
Private model/input/capture inspection is explicitly outside this receipt.
"""
import sys, pathlib, json, hashlib, datetime, collections, os
import requests
ROOT=pathlib.Path(os.environ.get('NFL_AUDIT_ROOT', pathlib.Path(__file__).resolve().parent))
WEBSITE=pathlib.Path(os.environ.get('NFL_AUDIT_WEBSITE_ROOT', ROOT/'website-audit'))
sys.path.insert(0,str(WEBSITE/'tools'))
import weekly_public_feed as f
import weekly_adaptive_overlay as o
base='https://nicknicky19.github.io/nicks-expert-nfl-picks/'
s=requests.Session()
def get(url,cap=4<<20):
    r=s.get(url,timeout=30);r.raise_for_status()
    assert len(r.content)<=cap
    return r.content
board_body=get(base+'data/week.json');board=json.loads(board_body)
pointer=json.loads(get(base+'data/weekly-adaptive-overlay.json'))
overlay_body=get(base+pointer['path']);overlay=json.loads(overlay_body)
policy=json.loads((WEBSITE/'config/weekly-derived-selected-policy-v2.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
feed=f.fetch_feed(policy,board,fetch=get)
selected,proof=f.validate_feed_v2(feed,policy,board,now=now,fetch=get)
original={o.key(r):r for r in selected['rows']}
assert len(original)==len(overlay['rows'])
checks=collections.Counter();traces=[]
for row in overlay['rows']:
    upstream=original[o.key(row)]
    assert {k:row[k] for k in o.ROW_FIELDS}=={k:upstream[k] for k in o.ROW_FIELDS}
    checks[row['category']]+=1
    if checks[row['category']]==1:
        traces.append({'category':row['category'],'product':row['product'],
            'identity_and_value_binding_sha256':o.digest({k:row[k] for k in o.ROW_FIELDS}),
            'upstream_consumer_exact':True})
receipt={'observed_at':now,'tls_verify':True,'state':'PASS_PUBLIC_FEED_TO_DEPLOYED_OVERLAY',
    'producer_feed_sha256':f.digest(feed),'upstream_execution':proof,'consumer_overlay_sha256':o.sha(overlay_body),
    'board_sha256':o.sha(board_body),'all_rows_exact':len(original),'category_counts':dict(checks),
    'representative_traces':traces,
    'limits':['Private inputs, fitted parameters and immutable restoration receipts not decoded here.',
              'Displayed values checked separately in live-browser.json; grading of these future games remains pending.',
              'This validates declared provenance, byte equality and consumer semantics; it is not independent model or accuracy reproduction.']}
(ROOT/'evidence/public-feed-trace.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
