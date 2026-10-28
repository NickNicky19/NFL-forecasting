"""Read actual HTTPS website bytes with normal TLS verification; no writes."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import os

os.umask(0o077)
BASE='https://nicknicky19.github.io/nicks-expert-nfl-picks/'
receipts=[]
def fetch(path):
    url=BASE+path
    with urlopen(Request(url, headers={'User-Agent':'NFL-owner-system-audit', 'Cache-Control':'no-cache'}), timeout=20) as response:
        assert response.status==200 and response.url==url
        raw=response.read((16<<20)+1)
        assert len(raw)<=16<<20
        receipts.append(dict(path=path,status=response.status,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        return raw

for path in ['index.html','app.js','style.css']:
    fetch(path)
board_raw=fetch('data/week.json'); board=json.loads(board_raw)
pointer=json.loads(fetch('data/weekly-adaptive-overlay.json'))
assert pointer['path'].startswith('data/weekly-adaptive/') and '..' not in pointer['path']
body=fetch(pointer['path'])
assert len(body)==pointer['bytes'] and hashlib.sha256(body).hexdigest()==pointer['sha256']
overlay=json.loads(body)
out=dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),purpose='ACTUAL_SERVED_HTTPS_WITH_NORMAL_TLS',
    assets=receipts,board=dict(season=board['season'],week=board['week'],generated_at=board['generated_at'],
        players=len(board['players']),games=len(board['games'])),
    overlay=dict(state=overlay['state'],rows=len(overlay['rows']),sha256=pointer['sha256']),
    new_source_or_selected_release_verified=False)
target=Path('/workspace/nfl-system-audit/continuation/evidence/website-live-assets-current32.json')
target.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
