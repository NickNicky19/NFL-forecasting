"""Prepare an exact review package against the committed Phase 2 assembly.

No website worktree is edited and no website branch is written. The preview is
supporting review evidence; installed-source CI and live acceptance remain due.
"""
from datetime import datetime, timezone
import copy
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path('/workspace/nfl-system-audit/continuation')
REPO = Path('/workspace/nfl-system-audit/website-combined-484d')
PARENT = '484dbeff5c3fb34673380bf52b0f30ee0354a521'
OUT = BASE / 'count-release-packet-phase2-484d-v3'
PREVIEW = OUT / 'preview'
OLD = BASE / 'count-release-packet-current-7' / 'preview'

def sha(body): return hashlib.sha256(body).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def blob(name): return subprocess.check_output(['git', 'show', PARENT+':'+name], cwd=REPO)
def write(name, body):
    path = PREVIEW/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
def replace(name, before, after):
    text = (PREVIEW/name).read_text()
    assert text.count(before) == 1, (name, before[:100])
    write(name, text.replace(before, after).encode())

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == PARENT
PREVIEW.mkdir(parents=True, exist_ok=False)
names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', PARENT], cwd=REPO, text=True).splitlines()
for name in names:
    if name.startswith(('pull/', 'tools/', 'config/', 'schemas/', 'tests/', '.github/workflows/')) or name in {
            'output/app.js', 'output/index.html', 'output/weekly-adaptive-overlay.js', 'output/reliability-ui.js'}:
        write(name, blob(name))
gitdir = subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=REPO, text=True).strip()
write('.git', ('gitdir: '+gitdir+'\n').encode())

# Preserve the successor helper and add only the three reviewed dispatch seams.
replace('tools/weekly_public_feed.py', 'def policy_check(policy):\n',
    'def policy_check(policy):\n    if policy.get("schema_version")=="weekly-derived-selected-policy-v4":\n'
    '        from weekly_public_feed_v4 import policy_check as check_v4\n        return check_v4(policy)\n')
replace('tools/weekly_public_feed.py', 'def validate_feed(feed,policy,board,*,now,fetch=None):\n',
    'def validate_feed(feed,policy,board,*,now,fetch=None):\n'
    '    if policy.get("schema_version")=="weekly-derived-selected-policy-v4":\n'
    '        from weekly_public_feed_v4 import validate_feed as validate_v4\n'
    '        return validate_v4(feed,policy,board,now=now,fetch=fetch or download)[0]\n')
replace('tools/weekly_public_feed.py',
    '    """Optional feed failure returns in-memory empty input; never reuses a stale descriptor."""\n',
    '    """Optional feed failure returns in-memory empty input; never reuses a stale descriptor."""\n'
    '    if policy.get("schema_version")=="weekly-derived-selected-policy-v4":\n'
    '        from weekly_public_feed_v4 import writer_input as write_v4\n'
    '        return write_v4(root,policy,board,website_source_sha=website_source_sha,now=now,feed=feed,fetch=fetch)\n')

# The Main-only candidate had a classic-only reader and 22-file inventory.
# This alternative binds the recognized current execution and full pipeline.
v4 = (OLD/'tools/weekly_public_feed_v4.py').read_text()
assert v4.count('from classic_model_v1 import contract\n') == 1
v4 = v4.replace('from classic_model_v1 import contract\n', '')
assert v4.count('CURRENT_CODE_FILES = old.CURRENT_CODE_FILES |') == 1
v4 = v4.replace('CURRENT_CODE_FILES = old.CURRENT_CODE_FILES |', 'CURRENT_CODE_FILES = old.PIPELINE_CODE_FILES |')
assert v4.count('return contract(root)') == 1
v4 = v4.replace('return contract(root)', 'return old.current_execution_contract(root)')
write('tools/weekly_public_feed_v4.py', v4.encode())
write('tests/test_weekly_public_feed_v4.py', (OLD/'tests/test_weekly_public_feed_v4.py').read_bytes())
replace('tests/test_weekly_public_feed_v4.py',
    "            path=root/'pull/scoring.py';raw=path.read_bytes();path.write_bytes(b'!'+raw[1:])\n",
    "            # The successor verifies original registrations from retained\n"
    "            # Git objects, not a copied policy file. Supply those actual\n"
    "            # independently hash-verified objects before corrupting code.\n"
    "            subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)\n"
    "            for oid,item in f.registration_objects(ROOT).items():\n"
    "                actual=subprocess.check_output(['git','-C',str(root),'hash-object','-w','-t',item['type'],'--stdin'],input=item['body']).decode().strip()\n"
    "                self.assertEqual(actual,oid)\n"
    "            path=root/'pull/scoring.py';raw=path.read_bytes();path.write_bytes(b'!'+raw[1:])\n")
replace('tests/test_weekly_public_feed_v4.py',
    "        self.assertEqual(f.CURRENT_CODE_FILES|{'tools/weekly_public_feed_v4.py'},v4.CURRENT_CODE_FILES)\n"
    "        self.assertEqual(len(v4.CURRENT_CODE_FILES),len(f.CURRENT_CODE_FILES)+1)\n",
    "        self.assertEqual(f.PIPELINE_CODE_FILES|{'tools/weekly_public_feed_v4.py'},v4.CURRENT_CODE_FILES)\n"
    "        self.assertEqual(len(v4.CURRENT_CODE_FILES),32)\n")

replace('tools/phase2_capture.py',
    '    policy = load_json(path)\n    weekly.policy_check_v3(policy, root=root)\n    return policy\n',
    '    policy = load_json(path)\n'
    '    if policy.get("schema_version") == "weekly-derived-selected-policy-v4":\n'
    '        import weekly_public_feed_v4 as current_weekly\n'
    '        current_weekly.policy_check(policy, root=root)\n'
    '    else:\n        weekly.policy_check_v3(policy, root=root)\n    return policy\n')

sys.path.insert(0, str(PREVIEW/'tools'))
import weekly_public_feed as feed
import weekly_public_feed_v4 as consumer
native = json.loads((BASE/'private/weekly-public-policy-7.json').read_bytes())
policy = consumer.template(PREVIEW)
policy.update(state='ROOT_REGISTERED', registered_at_utc=datetime.now(timezone.utc).isoformat(),
    lab_public_policy_sha256=sha(canonical(native)), lab_recipe_registered_at_utc=native['registered_at_utc'],
    recipe_registration_sha256=native['producer_policy_sha256'], producer_policy_sha256=native['producer_policy_sha256'],
    workflow_sha256=native['workflow_sha256'], jobs=native['jobs'], publication_authority=copy.deepcopy(native['publication_authority']))
consumer.policy_check(policy, root=PREVIEW, now=policy['registered_at_utc'])
assert len(policy['website_code_sha256']) == 32
assert policy['current_execution']['model'] == 'sleeper-matchup-classic-data-integrity-v2'
write('config/weekly-derived-selected-policy-v4.json', canonical(policy))
policy_sha = sha(canonical(policy))

# Preserve all V3 scientific fields; only its actual code inventory follows the
# changed executable bytes. Its old feed is not relabelled as COUNT-corrected.
prior = json.loads(blob('config/weekly-derived-selected-policy-v3.json'))
prior_static = {k:v for k,v in prior.items() if k != 'website_code_sha256'}
prior['website_code_sha256'] = {name:sha((PREVIEW/name).read_bytes()) for name in sorted(prior['website_code_sha256'])}
assert {k:v for k,v in prior.items() if k != 'website_code_sha256'} == prior_static
feed.policy_check_v3(prior, root=PREVIEW)
write('config/weekly-derived-selected-policy-v3.json', canonical(prior))

config = json.loads(blob('config/phase2.json'))
old_config = copy.deepcopy(config)
config['weekly_publication'] = dict(path='config/weekly-derived-selected-policy-v4.json', sha256=policy_sha)
assert {k:v for k,v in config.items() if k != 'weekly_publication'} == {k:v for k,v in old_config.items() if k != 'weekly_publication'}
write('config/phase2.json', (json.dumps(config, indent=2, sort_keys=True)+'\n').encode())
workflow = blob('.github/workflows/hourly.yml').decode()
workflow, count = re.subn(r'--feed-policy config/weekly-derived-selected-policy-v3.json --feed-policy-sha256 [a-f0-9]{64}',
    '--feed-policy config/weekly-derived-selected-policy-v4.json --feed-policy-sha256 '+policy_sha, workflow)
assert count == 1
write('.github/workflows/hourly.yml', workflow.encode())

# Keep the original pair-path checks and require the actual physical policy;
# the Phase 2 branch has a separately qualified current execution.
replace('tests/test_classic_build_pair_v1.py',
    "        policy=(ROOT/'config/weekly-derived-selected-policy-v3.json').read_bytes()\n"
    "        self.assertIn('--feed-policy config/weekly-derived-selected-policy-v3.json --feed-policy-sha256 '+hashlib.sha256(policy).hexdigest(),commands[feed])\n",
    "        import shlex\n"
    "        args=shlex.split(commands[feed][5:])\n"
    "        path=args[args.index('--feed-policy')+1]\n"
    "        schemas={'config/weekly-derived-selected-policy-v3.json':'weekly-derived-selected-policy-v3',\n"
    "                 'config/weekly-derived-selected-policy-v4.json':'weekly-derived-selected-policy-v4'}\n"
    "        self.assertIn(path,schemas)\n"
    "        policy=(ROOT/path).read_bytes();value=json.loads(policy)\n"
    "        self.assertEqual(args[args.index('--feed-policy-sha256')+1],hashlib.sha256(policy).hexdigest())\n"
    "        self.assertEqual(value['schema_version'],schemas[path])\n"
    "        import weekly_public_feed as weekly\n"
    "        if path.endswith('-v4.json'):\n"
    "            import weekly_public_feed_v4 as current_weekly\n"
    "            current_weekly.policy_check(value,root=ROOT)\n"
    "        else:weekly.policy_check_v3(value,root=ROOT)\n"
    "        self.assertEqual(value['current_execution'],weekly.current_execution_contract(ROOT))\n")
write('tests/test_weekly_public_feed_phase2_v4.py', (BASE/'count_phase2_v4_test_template.py').read_bytes())

changes = {}
for path in PREVIEW.rglob('*'):
    if not path.is_file() or '__pycache__' in path.parts or path.name == '.git': continue
    name = path.relative_to(PREVIEW).as_posix()
    raw = path.read_bytes()
    if name not in names or raw != blob(name): changes[name] = raw

def tree_hash(tree, updates):
    entries={}
    for row in subprocess.check_output(['git','ls-tree','-z',tree],cwd=REPO).split(b'\0'):
        if not row:continue
        meta,name=row.split(b'\t',1);mode,kind,oid=meta.split()
        entries[name]=(mode.lstrip(b'0'),kind,oid.decode())
    for name in {n.split('/',1)[0] for n in updates}:
        key=name.encode();old=entries.get(key)
        direct=updates.get(name)
        if direct is not None:
            entries[key]=(old[0] if old else b'100644',b'blob',hashlib.sha1(b'blob '+str(len(direct)).encode()+b'\0'+direct).hexdigest())
        else:
            assert old and old[1]==b'tree'
            entries[key]=(old[0],b'tree',tree_hash(old[2],{k.split('/',1)[1]:v for k,v in updates.items() if k.startswith(name+'/')}))
    encoded=b''.join(mode+b' '+name+b'\0'+bytes.fromhex(oid) for name,(mode,kind,oid) in
        sorted(entries.items(),key=lambda item:item[0]+(b'/' if item[1][1]==b'tree' else b'')))
    return hashlib.sha1(b'tree '+str(len(encoded)).encode()+b'\0'+encoded).hexdigest()

patch=[];manifest=[]
for name,raw in sorted(changes.items()):
    before=blob(name) if name in names else b''
    before_path=OUT/('before-'+name.replace('/','--'));before_path.write_bytes(before)
    diff=subprocess.run(['diff','-u','--label','a/'+name if name in names else '/dev/null',
        '--label','b/'+name,str(before_path),str(PREVIEW/name)],capture_output=True)
    assert diff.returncode==1
    patch.append(diff.stdout)
    manifest.append(dict(path=name,before_sha256=sha(before) if name in names else None,sha256=sha(raw),bytes=len(raw),
        git_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()))
patch_body=b''.join(patch)
(OUT/'binding.patch').write_bytes(patch_body)
(OUT/'binding.patch.gz').write_bytes(gzip.compress(patch_body,mtime=0))
(OUT/'PUBLIC-native-policy.json').write_bytes(canonical(native))
parent_tree=subprocess.check_output(['git','rev-parse',PARENT+'^{tree}'],cwd=REPO,text=True).strip()
handoff=dict(schema_version='count-consumer-phase2-source-handoff-v1',state='PREPARED_NOT_INSTALLED',
    source_parent=PARENT,source_parent_tree=parent_tree,expected_tree=tree_hash(parent_tree,changes),file_manifest=manifest,
    patch_sha256=sha(patch_body),website_policy_sha256=policy_sha,website_policy_prepared_at=policy['registered_at_utc'],
    lab_source_sha=native['source_sha'],lab_public_policy_sha256=policy['lab_public_policy_sha256'],
    lab_recipe_sha256=policy['producer_policy_sha256'],code_inventory_files=len(policy['website_code_sha256']),
    website_worktree_edited=False,new_fits=0,original_registrations_preserved=True,
    alternative_to_main_packet=True,blind_stacking_permitted=False,
    remaining=['existing owner protected-source binding','actual combined-source CI','normal release','live selected-feed consumption'])
(OUT/'HANDOFF.json').write_text(json.dumps(handoff,indent=2)+'\n')
print(json.dumps({k:handoff[k] for k in ('state','source_parent','expected_tree','patch_sha256','website_policy_sha256','code_inventory_files')}))
