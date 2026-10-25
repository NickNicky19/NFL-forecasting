"""External scratch-only observation: no reader/source/registration changes."""
import hashlib
import json
import os
from pathlib import Path
import sys

DEST=Path(os.environ['RETAINED_DIAGNOSTIC_DIR'])
DEST.mkdir(parents=True,exist_ok=True)
SEEN=set()

def append(value):
    with (DEST/('trace-'+str(os.getpid())+'.jsonl')).open('a') as stream:
        stream.write(json.dumps(value,sort_keys=True)+'\n')

def deny_network(event,args):
    if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:
        raise RuntimeError('REAL_NETWORK_FORBIDDEN_IN_FICTIONAL_REPLAY')
    if event=='subprocess.Popen':
        executable,argv=args[:2]
        if Path(str(executable)).name=='git' and isinstance(argv,(list,tuple)):
            skip=False
            for part in argv[1:]:
                if skip:skip=False;continue
                if part in {'-C','-c','--git-dir','--work-tree'}:skip=True;continue
                if str(part).startswith('-'):continue
                if part in {'fetch','push','pull','clone','ls-remote'}:
                    raise RuntimeError('GIT_NETWORK_FORBIDDEN_IN_FICTIONAL_REPLAY')
                break
sys.addaudithook(deny_network)

def local(frame,event,arg):
    if event!='exception':return local
    error=arg[1]
    if 'recording source differs from closed engine' not in str(error).lower():return local
    values=frame.f_locals
    key=(frame.f_code.co_filename,values.get('commit'),values.get('name'))
    if key in SEEN:return local
    SEEN.add(key)
    row=dict(kind='EXACT_SOURCE_MISMATCH',pid=os.getpid(),module=frame.f_code.co_filename,
        function=frame.f_code.co_name,line=frame.f_lineno,requested_commit=values.get('commit'),
        repository=str(values.get('repository')),code_path=values.get('name'),expected_sha256=values.get('expected'),
        error_type=type(error).__name__,error=str(error))
    raw=values.get('raw')
    name=values.get('name','')
    if isinstance(raw,bytes) and name.startswith(('pull/','tools/')) and name.endswith('.py'):
        row['actual_sha256']=hashlib.sha256(raw).hexdigest()
        folder=DEST/'preimages';folder.mkdir(exist_ok=True)
        stem=str(os.getpid())+'-'+name.replace('/','_')
        actual=folder/(stem+'.actual.py');actual.write_bytes(raw);row['actual_preimage']=str(actual)
        expected_path=Path(frame.f_globals['ROOT'])/name
        if expected_path.is_file():
            body=expected_path.read_bytes();target=folder/(stem+'.expected.py');target.write_bytes(body)
            row.update(expected_file_sha256=hashlib.sha256(body).hexdigest(),expected_preimage=str(target))
    stack=[];parent=frame.f_back
    while parent is not None and len(stack)<12:
        item=dict(function=parent.f_code.co_name,module=parent.f_code.co_filename,line=parent.f_lineno)
        for name in ('inputs','saved','plan','payload'):
            value=parent.f_locals.get(name)
            if isinstance(value,dict):
                item[name]={k:value[k] for k in ('schema_version','model','code_commit','source_sha')
                    if k in value and isinstance(value[k],(str,int,bool,type(None)))}
        stack.append(item);parent=parent.f_back
    row['stack']=stack
    append(row)
    return local

def trace(frame,event,arg):
    if event=='call':
        name=frame.f_code.co_name
        if name in {'fit','partial_fit','fit_transform','train'} or name.startswith('fit_'):
            raise RuntimeError('FITTING_FORBIDDEN_IN_FICTIONAL_REPLAY')
        if name=='recording_source' and frame.f_code.co_filename.endswith('data_integrity_v2.py'):
            frame.f_trace_lines=False
            return local
    return None
sys.settrace(trace)
