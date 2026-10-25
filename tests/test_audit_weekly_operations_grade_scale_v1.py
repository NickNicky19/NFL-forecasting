"""One exact 18k-candidate/5k-selected fictional native-capacity probe.

The original fixture generator is reused with its cardinality/player role
changed. R0 controls use their supported public_release field rather than the
fixture-only redundant public_export_authorized field. All rows remain.
No production code/cap/row validation is replaced.
Current/archive authority uses the SAME explicitly fictional seams as the small
cold integration test. A capacity failure remains a failing release test.
"""
import ast
from copy import deepcopy
import gzip
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from nfl_lab import private_draft_store as store
from nfl_lab import audit_weekly_operations_grade_v1 as worker
import test_audit_weekly_grade_v1 as original
import test_audit_weekly_operations_grade_v1 as bridge

ROOT=Path(__file__).resolve().parents[1]


def full_scope_fixture(root):
    tree=ast.parse(Path(original.__file__).read_text())
    packet=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='packet')
    packet=deepcopy(packet);packet.decorator_list=[]
    class Cardinality(ast.NodeTransformer):
        def __init__(self):self.counts=dict(queries=0,position=0,rows=0,expected_rows=0,issued_rows=0,control_metadata=0)
        def visit_Delete(self,node):
            self.generic_visit(node)
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript)and isinstance(node.targets[0].slice,ast.Constant)and node.targets[0].slice.value=='scientific_qualification':
                target=deepcopy(node.targets[0]);target.slice=ast.Constant('public_export_authorized')
                node.targets.append(target);self.counts['control_metadata']+=1
            return node
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name)and node.func.id=='range'and len(node.args)==1 and isinstance(node.args[0],ast.Constant)and node.args[0].value==3:
                node.args[0]=ast.Constant(1000);self.counts['queries']+=1
            if isinstance(node.func,ast.Name)and node.func.id=='dict':
                for key in node.keywords:
                    if key.arg=='position'and isinstance(key.value,ast.Constant)and key.value.value=='RB':
                        key.value=ast.Constant('QB');self.counts['position']+=1
                    if key.arg in {'rows','expected_rows','issued_rows'}and isinstance(key.value,ast.Constant)and key.value.value==3:
                        key.value=ast.Constant(1000);self.counts[key.arg]+=1
            return node
    change=Cardinality();packet=change.visit(packet)
    assert change.counts==dict(queries=1,position=1,rows=1,expected_rows=1,issued_rows=1,control_metadata=1)
    namespace=dict(vars(original))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[packet],type_ignores=[])),'fictional-full-cardinality-fixture','exec'),namespace)
    result=namespace['packet'](root)
    aliases=result['restored']['aliases']
    candidates=[r for name,r in aliases.items()if name.startswith('runtime/candidates/')and name.endswith('.jsonl.gz')]
    counts=[len(gzip.decompress(Path(ref['path']).read_bytes()).splitlines())for ref in candidates]
    assert len(candidates)==18 and counts==[1000]*18
    selected=gzip.decompress(Path(aliases['runtime/selected.jsonl.gz']['path']).read_bytes()).splitlines()
    assert len(selected)==5000 and len(result['query'])==1000
    assert {json.loads(row)['category']for row in selected}=={'pass_yd','pass_td','pass_cmp','pass_att','pass_int'}
    assert len(json.loads(Path(aliases['r0/control_forecast_rows.json']['path']).read_bytes())['rows'])==5000
    return result


def test_full_18000_candidate_5000_selected_scope_under_native_512MiB(tmp_path,monkeypatch):
    monkeypatch.setattr(bridge,'grade_packet',SimpleNamespace(__wrapped__=full_scope_fixture))
    x=bridge.pipeline.__wrapped__(tmp_path,monkeypatch);q=x.q;f=q['f']
    seed=dict(root=str(x.root),work=str(tmp_path/'cold-transport'),cache=str(q['storage'].cache),state_root=str(q['storage'].state_root),
        restored=x.restored,restored_ref=x.context(worker.PHASES[0]).request['inputs']['archive_restored'],
        epoch=q['r'].epoch.document,completion=q['r'].completion,original_choice=f['raw'].decode(),original_completion=f['completion'],
        slate=f['slate'],catalog=f['catalog'],policy=f['policy'],history_binding=f['history_binding'],choice=q['c'].document,
        replay=f['replay'],schedule=q['schedule'],query=q['query'])
    seed_path=tmp_path/'fictional-full-scope.json';seed_path.write_bytes(store.canonical(seed))
    tree=ast.parse(Path(bridge.__file__).read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='test_cold_provider_grade_write_and_fresh_read_each_under_actual_512MiB')
    script=next(ast.literal_eval(n.value)for n in function.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='script'for t in n.targets))
    instrument='''
def capacity(label):
    values={}
    for line in Path('/proc/self/status').read_text().splitlines():
        key,_,value=line.partition(':')
        if key in {'VmSize','VmPeak','VmRSS','VmHWM'}:values[key]=int(value.split()[0])*1024
    print(json.dumps(dict(fictional=True,capacity_stage=label,CPU_seconds=time.process_time(),**values)),flush=True)
def measured(module,name):
    actual=getattr(module,name)
    def call(*args,**kwargs):
        capacity('BEFORE_'+name)
        result=actual(*args,**kwargs)
        capacity('AFTER_'+name)
        return result
    setattr(module,name,call)
import time
capacity('IMPORTS_AND_TYPED_EPOCH_READY')
for module,name in [(grade,'bind_capture'),(grade,'grade'),(checkpoint,'append'),(checkpoint,'restore')]:measured(module,name)
'''
    anchor='if phase=="write":\n    result=worker.execute'
    assert script.count(anchor)==1
    script=script.replace(anchor,instrument+'\n'+anchor)
    profile=json.loads((ROOT/'config/audit-weekly-numerical-runtime-v1.json').read_bytes())['environment']
    for phase in ('write','read'):
        result=subprocess.run([sys.executable,'-B','-c',script,str(seed_path),phase],cwd=ROOT,
            env=dict(PYTHONDONTWRITEBYTECODE='1',**profile),capture_output=True,text=True,timeout=185)
        print(result.stdout,end='',flush=True)
        if result.returncode:print(result.stderr,end='',file=sys.stderr,flush=True)
        assert result.returncode==0,(phase,result.stderr)
        value=json.loads(result.stdout.splitlines()[-1]);assert value['AS_bytes']==512 << 20 and value['VmPeak']<=512 << 20
