import ast,csv,errno,hashlib,itertools,json,os,pathlib,stat,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath,PureWindowsPath
from types import SimpleNamespace
from unittest.mock import patch
source,output,counterpart=map(Path,sys.argv[1:4]);sys.path.insert(0,str(source))
from nfl_lab import operational_storage as s
baseline='3341a9c2a339c141e8f4c87cd1d17515f5dc3d4d'
def original_file(name):
    return subprocess.check_output(['git','--no-lazy-fetch','show',baseline+':'+name],cwd=source)
def sha(body):return hashlib.sha256(body).hexdigest()
files=['nfl_lab/operational_storage.py','tests/test_storage_path_guards.py']
hashes={name:sha((source/name).read_bytes()) for name in files}
assert all((source/name).read_bytes()==(counterpart/name).read_bytes() for name in files)
before=ast.parse(original_file(files[0]));after=ast.parse((source/files[0]).read_bytes())
helpers={'_beneath','_no_symlinks'}
original={n.name:n for n in before.body if isinstance(n,ast.FunctionDef) and n.name in helpers}
namespace={'StorageIntegrityError':s.StorageIntegrityError}
exec(compile(ast.Module(list(original.values()),[]),'original-storage-helpers','exec'),namespace)
def other_nodes(tree):
    return ast.dump(ast.Module([n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name in helpers) and not (isinstance(n,ast.Import) and [x.name for x in n.names]==['errno'])],[]),include_attributes=False)
assert other_nodes(before)==other_nodes(after)
def outcome(fn,*args):
    try:return ('ok',fn(*args))
    except Exception as e:return (type(e).__name__,str(e),getattr(e,'errno',None),getattr(e,'winerror',None))
texts=['.','','a','A','a/b','a/b/c','a/../b','../a','/','//','/a','/A','/a/b','//a/b','/a/b/c','C:','c:','C:/','C:/A','c:/a/b','D:/a/b','C:a','C:a/b','\\\\server\\share','\\\\server\\share\\A\\b']
paths=[cls(x) for cls in (PurePosixPath,PureWindowsPath) for x in texts]
mismatches=[];pairs=0
with (output/'containment.csv').open('x',newline='') as stream:
    writer=csv.writer(stream);writer.writerow(['path_flavor','path','root_flavor','root','original','candidate','match'])
    for p,r in itertools.product(paths,repeat=2):
        a=outcome(namespace['_beneath'],p,r);b=outcome(s._beneath,p,r);pairs+=1
        writer.writerow([type(p).__name__,str(p),type(r).__name__,str(r),json.dumps(a),json.dumps(b),a==b])
        if a!=b:mismatches.append([repr(p),repr(r),a,b])
assert not mismatches,mismatches[:5]
exceptions=[]
for number,win in itertools.product([None,errno.ENOENT,errno.ENOTDIR,errno.EBADF,errno.ELOOP,errno.EACCES,errno.EPERM,errno.EIO,errno.EAGAIN],[None,21,123,1921,0,5,'123']):
    error=OSError(number,'synthetic ancestor error')
    if win is not None:error.winerror=win
    exceptions.append(error)
exceptions.extend([ValueError('synthetic path encoding error'),UnicodeEncodeError('utf-8','\ud800',0,1,'synthetic')])
no_paths=[Path('.'),Path('a/b/c'),Path('/'),Path('//server/share/leaf'),Path('/a/b/c'),Path('../a'),Path('a/../b')]
checked=0
for path in no_paths:
    for fault in range(len([path,*path.parents])):
        for error in [None,*exceptions,'symlink']:
            receipts=[]
            for fn in [namespace['_no_symlinks'],s._no_symlinks]:
                calls=[]
                def fake(name,*,follow_symlinks=True,**kwargs):
                    assert follow_symlinks is False;calls.append(os.fspath(name))
                    if len(calls)-1==fault:
                        if error=='symlink':return SimpleNamespace(st_mode=stat.S_IFLNK)
                        if error is not None:raise error
                    return SimpleNamespace(st_mode=stat.S_IFDIR)
                with patch.object(os,'stat',fake):result=outcome(fn,path)
                receipts.append((result,calls))
            assert receipts[0]==receipts[1],(path,fault,repr(error),receipts)
            checked+=1
with tempfile.TemporaryDirectory(prefix='storage-guard-fictional-') as name:
    root=Path(name);(root/'real').mkdir();(root/'file').write_bytes(b'fictional')
    (root/'linked').symlink_to(root/'real',target_is_directory=True);(root/'broken').symlink_to(root/'missing');(root/'loop').symlink_to(root/'loop')
    cases=[root/'real',root/'file'/'child',root/'missing'/'child',root/'linked',root/'linked'/'missing'/'leaf',root/'broken',root/'broken'/'child',root/'loop',root/'loop'/'child']
    for path in cases:assert outcome(namespace['_no_symlinks'],path)==outcome(s._no_symlinks,path),path
baseline_unchanged=['nfl_lab/audit_weekly_grade_v1.py','tests/test_audit_weekly_grade_native_memory_v1.py']
assert all(original_file(name)==(source/name).read_bytes() for name in baseline_unchanged)
assert hashes=={name:sha((source/name).read_bytes()) for name in files}
report=dict(schema_version='independent-storage-path-guards-review-v1',state='PASS',observed_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.version.split()[0],original_baseline_commit=baseline,source_worktree=str(source),counterpart_worktree=str(counterpart),files_sha256=hashes,counterpart_files_identical=True,containment=dict(pairs=pairs,mismatches=len(mismatches),matrix='containment.csv'),symlink=dict(differential_scenarios=checked,real_filesystem_cases=len(cases),all_matched=True,checks=['leaf-to-root stat order','follow_symlinks=False','symlink rejection ancestor/message','errno suppression and propagation','winerror suppression and propagation','ValueError and UnicodeEncodeError handling'],original_ignored_errnos=list(pathlib._IGNORED_ERRNOS),original_ignored_winerrors=list(pathlib._IGNORED_WINERRORS)),other_storage_AST_identical_to_baseline=True,grader_and_native_test_identical_to_baseline=True,repository_edits=0,remote_calls=0,native_tests_run=0,protected_outcome_reads=0,fits=0)
with (output/'REVIEW.json').open('x') as stream:json.dump(report,stream,indent=2,sort_keys=True);stream.write('\n')
print('PASS: containment 2500/2500; mocked symlink scenarios 1407/1407; real filesystem cases 9/9')
print(json.dumps(report,sort_keys=True))
