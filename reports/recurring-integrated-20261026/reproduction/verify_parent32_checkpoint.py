"""Read-only current-source metadata check; no private outcome decoding or POST."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import argparse, gzip, hashlib, json, os, subprocess, sys

os.umask(0o077)
BASE = Path('/workspace/nfl-system-audit')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=BASE/'producer-native31-20261028')
parser.add_argument('--receipt-name',default='parent32-checkpoint-metadata-preflight.json')
args=parser.parse_args()
SOURCE = args.source.resolve()
sys.path.insert(0, str(SOURCE))
from nfl_lab import audit_weekly_grade_history_v1 as history, audit_weekly_template_v1 as template

GH = str(BASE/'bin/gh')
def get(path):
    return json.loads(subprocess.check_output([GH, 'api', 'repos/NickNicky19/NFL-forecasting/'+path]))

root = json.loads((BASE/'continuation/private/weekly-go-32.json').read_bytes())
packed_receipt = (BASE/'continuation/private/consumer32-actual-fresh-board/public-network-4.bin').read_bytes()
assert hashlib.sha256(packed_receipt).hexdigest() == 'b511c17b78bcfe215188365131fc93c17f4cd8b4087a66e19758a4dfaae09b72'
receipt = json.loads(gzip.decompress(packed_receipt))
head = get('branches/lab-state')['commit']['sha']
path = 'state/controller-v1/grade-checkpoints/'+receipt['feed_sha256']+'.json.gz'
url = 'https://raw.githubusercontent.com/NickNicky19/NFL-forecasting/'+head+'/'+path
with urlopen(Request(url, headers={'User-Agent':'NFL-readonly-audit'}), timeout=20) as response:
    assert response.status == 200 and response.url == url
    packed = response.read((64<<10)+1)
assert len(packed) <= 64<<10
assert hashlib.sha256(packed).hexdigest() == '6f3d4919a085c4a414fe7aab448a2d3aee2646bb74dfd8393e77d8a2c5984cdd'
saved = BASE/'continuation/private/parent32-public-sidecar.json.gz'
if saved.exists(): assert saved.read_bytes() == packed
else:
    with saved.open('xb') as stream: stream.write(packed)
listing = get('actions/runs/40644670107/jobs?per_page=100')['jobs']
jobs = {role:next(j for j in listing if j['id']==ref['api_job_id']) for role,ref in receipt['jobs'].items()}
now = datetime.now(timezone.utc).isoformat()
parsed = history.validate_parent_sidecar(packed, receipt=receipt, qualified_runtime=root['qualified_runtime'],
    code_pins=root['code_pins'], jobs=jobs, at=now)
assert all(parsed[k]==receipt[k] for k in ('feed_sha256','source_sha','run_id','root_go_sha256','workflow_sha256','epoch_sha256'))
entries=get('contents/'+history.LOCATOR_ROOT+'?ref='+head)
name=history.latest_locator(entries)
locator_url='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting/'+head+'/'+history.LOCATOR_ROOT+'/'+name
with urlopen(Request(locator_url,headers={'User-Agent':'NFL-readonly-audit'}),timeout=20) as response:
    assert response.status==200 and response.url==locator_url
    locator_raw=response.read(history.LIMITS['sidecar_bytes']+1)
assert len(locator_raw)<=history.LIMITS['sidecar_bytes']
locator=history.metadata_document(locator_raw)
assert locator['cohort']['run_id']==receipt['run_id'] and locator['anchor']['feed_sha256']==receipt['feed_sha256']
package,_=template.checkpoint_runtime(root,locator['sidecar']['checkpoint_handoff'],anchor=locator['anchor'],
    checkpoint=dict(schema_version=history.LOCATOR_REF,path=name,sha256=hashlib.sha256(locator_raw).hexdigest()))
history.locator_metadata(locator_raw,receipt=receipt,qualified_runtime=package,code_pins=root['code_pins'],jobs=jobs,at=now)
out = dict(schema_version='audit-parent32-current-metadata-preflight-v1', observed_at_utc=now,
    state='CURRENT_SOURCE_PARENT_SIDECAR_METADATA_PASS', source=receipt['source_sha'],
    capture_run=int(receipt['run_id']), lab_state_commit=head, sidecar_path=path,
    sidecar_sha256=hashlib.sha256(packed).hexdigest(), receipt_sha256=hashlib.sha256(packed_receipt).hexdigest(),
    three_actual_completed_successful_jobs=True, exact_root_workflow_epoch_feed_bindings=True,
    checkpoint_or_outcome_bodies_decoded=False, private_assets_read=0, remote_writes=0,
    parent_execution_pass=False, private_restore_authority_minted=False,
    limitation='Offline metadata preflight only. Actual Parent must authenticate the latest history locator, private native evidence, current capacity/source/clock and one-issue claim before enqueue.')
out['validator_checkout']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
out['validator_module_sha256']=hashlib.sha256((SOURCE/'nfl_lab/audit_weekly_grade_history_v1.py').read_bytes()).hexdigest()
out['compatibility_check_only']=True
out['actual_latest_history_locator_metadata']='PASS'
out['history_locator_path']=history.LOCATOR_ROOT+'/'+name
out['history_locator_sha256']=hashlib.sha256(locator_raw).hexdigest()
target = BASE/'continuation/evidence'/args.receipt_name
with target.open('x') as stream: json.dump(out,stream,indent=2);stream.write('\n')
print(json.dumps(out))
