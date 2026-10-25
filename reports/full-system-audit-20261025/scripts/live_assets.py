"""Read-only public asset identity check. Emits no individual forecast rows."""
import hashlib, json, pathlib, re, datetime, os
import requests

ROOT = pathlib.Path(os.environ.get('NFL_AUDIT_ROOT', pathlib.Path(__file__).resolve().parent))
BASE = 'https://nicknicky19.github.io/nicks-expert-nfl-picks/'
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)
receipt = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'tls_verify': True, 'assets': {}}
session = requests.Session()
def fetch(path, local=None):
    r = session.get(BASE + path, timeout=30)
    r.raise_for_status()
    b = r.content
    entry = {'status': r.status_code, 'bytes':len(b), 'sha256':hashlib.sha256(b).hexdigest(),
             'content_type':r.headers.get('content-type'), 'etag':r.headers.get('etag'),
             'last_modified':r.headers.get('last-modified'), 'url':r.url}
    if local:
        entry['matches_checkout'] = (ROOT / 'website-audit' / 'output' / local).read_bytes() == b
    receipt['assets'][path] = entry
    return b

index = fetch('', 'index.html').decode()
for path in re.findall(r'(?:src|href)="([^"]+)"', index):
    if path.startswith(('http', 'data:', '#')): continue
    fetch(path, path.split('?')[0])
board_bytes = fetch('data/week.json', 'data/week.json')
board = json.loads(board_bytes)
pointer = json.loads(fetch('data/weekly-adaptive-overlay.json', 'data/weekly-adaptive-overlay.json'))
assert re.fullmatch(r'data/weekly-adaptive/[a-f0-9]{64}\.json', pointer['path'])
overlay_bytes = fetch(pointer['path'], pointer['path'])
overlay = json.loads(overlay_bytes)
assert hashlib.sha256(overlay_bytes).hexdigest() == pointer['sha256']
assert len(overlay_bytes) == pointer['bytes']
assert hashlib.sha256(board_bytes).hexdigest() == overlay['display_board_sha256'] == pointer['display_board_sha256']
import sys
sys.path.insert(0,str(ROOT / 'website-audit' / 'tools'))
import weekly_adaptive_overlay as consumer
consumer.validate_overlay(overlay, board, hashlib.sha256(board_bytes).hexdigest())
from collections import Counter
receipt['contract'] = {'status':'PASS', 'season':board['season'], 'week':board['week'],
    'board_generated_at':board['generated_at'], 'overlay_prepared_at':overlay['prepared_at'],
    'overlay_packaged_at':overlay['packaged_at'], 'website_source_sha':overlay['website_source_sha'],
    'selected_rows':len(overlay['rows']), 'categories':dict(Counter(r['category'] for r in overlay['rows'])),
    'games':len(set(r['game_id'] for r in overlay['rows'])), 'fallback_counts':overlay['fallback_counts']}
(OUT / 'live-assets.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
