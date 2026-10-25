"""Recover exact source prerequisites, without changing the pending writer tree.

Never substitutes main's newer policy for the immutable Phase 2 historical one.
Missing protected proposals remain missing; digests cannot recover absent bytes.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
PACKAGE=Path(__file__).resolve().parents[1]
AUDIT=PACKAGE.parent
SOURCE=AUDIT/'website-phase2'
BASE='e415912b9c3d3ff52e8f435517af02e794d97fa4'
HISTORICAL='315be5e86a1a3a93022b68c453739076487e2077'
SCRATCH=Path('/tmp/nfl-phase2-source-reconstruction-e415912')
ENV=dict(os.environ,GIT_OPTIONAL_LOCKS='0',PYTHONDONTWRITEBYTECODE='1')
def sha(value):return hashlib.sha256(value).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(SOURCE),*args],env=ENV,stderr=subprocess.PIPE)
def main():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    # Source directories only; no provider caches, forecast or outcome bodies.
    if not SCRATCH.exists():
        shutil.copytree(SOURCE,SCRATCH,ignore=shutil.ignore_patterns('.git','data','__pycache__'))
    else:
        assert (SCRATCH/'tools/weekly_public_feed.py').read_bytes()==(SOURCE/'tools/weekly_public_feed.py').read_bytes()
    recovered={}
    for name,expected in {
        'config/weekly-derived-selected-policy-v2.json':'45e51a07a077ce0aedede608fcef2ddb3592828a0734843d37a3991e6673a546',
        'output/weekly-adaptive-overlay.js':'d6657e82639aa001f64701672e25cc72bd6e55142127669a59396f9efe485a68',
        'schemas/weekly-derived-selected-feed-v2.json':'68709b6cb3d9a420835fcd74ee5dd5392ae83c36f54cce985fcd0fa47c372db5',
        'schemas/weekly-derived-selected-feed-v1.json':'831604c59ab80d979620b935ab50496d6f28ff989849141749b31a6a788c20f8',
        'config/weekly-derived-selected-policy-v1.json':'0bcdf8505d2f0d268ea97e5c17c26f2a8d7cb91ef2e089cd9e410f27eb36f1ae',
    }.items():
        assert not (SOURCE/name).exists()
        raw=git('show',HISTORICAL+':'+name)
        assert sha(raw)==expected
        for root in [SCRATCH,PACKAGE/'phase2/recovered-files']:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        recovered[name]=dict(sha256=expected,bytes=len(raw),exact_retained_commit=HISTORICAL,
                              present_in_pending_snapshot=False)
    # Read/hash actual installed inline controller; never execute the workflow.
    name='.github/workflows/prepare-diagnostic-seed.yml'
    raw=(SOURCE/name).read_bytes()
    start=b'          import datetime as dt, gzip, hashlib, json, math, os, re, resource, signal, stat, subprocess, sys, tarfile, time\n'
    end=b"          if __name__=='__main__':main()\n"
    assert raw.count(start)==raw.count(end)==1
    block=raw[raw.index(start):raw.index(end)+len(end)]
    controller=b''.join((line[10:]if line.startswith(b'          ')else b'')+b'\n'for line in block.splitlines())
    assert sha(controller)=='2ee6d870c3bb6c8e667eae3a49cadf22220d6ab21d0c990c8035332d1deadfaf'
    assert len(controller)==30854
    want={'c06a283d1e48414129c0e57adeaf0ea718d47d203aefabee5652e1e084adfbd3',
          '78ada1900f8147d3a9d2a3d6c9ec46d40a302946f00082cc614dafa1544f0da8',
          '2f4d7f7eac10c4c82a56762929e5d3d8f853493f5b01edbee2925adf158b501e'}
    paths=['.github/workflows/hourly.yml',name]
    commits=git('log','--all','--format=%H','--',*paths).decode().splitlines()
    bodies=set();matches=[]
    for commit in commits:
        for path in paths:
            try:body=git('show',commit+':'+path)
            except subprocess.CalledProcessError:continue
            digest=sha(body)
            if digest in bodies:continue
            bodies.add(digest)
            if digest in want:matches.append(dict(commit=commit,path=path,sha256=digest))
            if start in body and end in body:
                block=body[body.index(start):body.index(end)+len(end)]
                driver=b''.join((line[10:]if line.startswith(b'          ')else b'')+b'\n'for line in block.splitlines())
                if sha(driver) in want:matches.append(dict(commit=commit,path=path,controller_sha256=sha(driver)))
    # Local retained PR exports contain the target digests/status, not a workflow
    # body or an exact transformation. Preserve that distinction in the result.
    comments=json.loads((AUDIT/'evidence/continuation-comments.json').read_text())
    claims=[]
    for c in comments:
        if c.get('id') in [6391031941,6391181916]:
            claims.append(dict(comment_id=c['id'],body_sha256=sha(c['body'].encode()),
                              workflow_bytes_in_export=False,
                              asserted_reconstructable_in_prior_actor_context=True))
    record=dict(source_base=BASE,recovered_files=recovered,
        current_main_v2_policy_is_not_historical_phase2_policy=True,
        installed_controller=dict(path=name,bytes=len(controller),sha256=sha(controller)),
        exact_proposals_not_found=dict(hourly_sha256='c06a283d1e48414129c0e57adeaf0ea718d47d203aefabee5652e1e084adfbd3',
            prepare_sha256='78ada1900f8147d3a9d2a3d6c9ec46d40a302946f00082cc614dafa1544f0da8',
            raw_controller_sha256='2f4d7f7eac10c4c82a56762929e5d3d8f853493f5b01edbee2925adf158b501e',raw_controller_bytes=35468),
        retained_workflow_search=dict(changing_commits=len(commits),unique_bodies=len(bodies),matches=matches),
        retained_claims=claims,missing_input='Exact protected hourly and preparation workflow bodies, or a complete authenticated deterministic recipe and its base inputs. Target hashes alone are insufficient.',
        v3_policy='Deterministically derivable from immutable historical policy + actual integrated code and recognized current execution; prior exact physical candidate digest/body is absent. Do not copy e415912 policy onto main corrections.',
        writer_run_user_reported='NFL-WEB-RANKINGS-PHASE2-20261025-003000Z',
        coordination_user_reported='5f7510a',remote_lease_read_or_modified=False,
        outcomes_read=False,website_mutations=False)
    (PACKAGE/'phase2/reconstruction.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(recovered=len(recovered),workflow_matches=matches,scratch=str(SCRATCH))))
if __name__=='__main__':main()
