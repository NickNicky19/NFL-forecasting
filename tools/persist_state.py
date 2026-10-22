"""Publish only derived lab state on its dedicated branch; never source feeds."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def git(*args,cwd=None,capture=False):
    return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=capture).stdout


root=Path.cwd();state=root/"state"
if not list(state.glob("forecasts/*.json.gz")):
    print("No derived forecast state to persist");sys.exit(0)
branch="lab-state"
with tempfile.TemporaryDirectory(prefix="nfl-lab-state-") as temp:
    target=Path(temp)
    try:
        remote=git("rev-parse","refs/remotes/origin/"+branch,capture=True).strip()
        git("worktree","add","--detach",str(target),remote)
    except subprocess.CalledProcessError:
        git("worktree","add","--detach",str(target),"HEAD")
        git("checkout","--orphan",branch,cwd=target)
        git("rm","-rf","--ignore-unmatch",".",cwd=target)
    shutil.copytree(state,target/"state",dirs_exist_ok=True,ignore=shutil.ignore_patterns(".writer.lock"))
    git("add","state",cwd=target)
    if subprocess.run(["git","diff","--cached","--quiet"],cwd=target).returncode==0:
        print("Idempotent: no new evidence");sys.exit(0)
    git("-c","user.name=NFL lab","-c","user.email=nfl-lab@users.noreply.github.com","commit","-m","Append immutable NFL lab observations",cwd=target)
    commit=git("rev-parse","HEAD",cwd=target,capture=True).strip()
    git("push","origin",f"HEAD:refs/heads/{branch}",cwd=target)
    observed=git("ls-remote","origin",f"refs/heads/{branch}",capture=True).split()[0]
    if observed!=commit:raise RuntimeError("remote state readback mismatch")
    subprocess.run([sys.executable,"-m","nfl_lab.cli","publication","--state",str(state),"--publication-commit",commit],check=True)
    shutil.copytree(state,target/"state",dirs_exist_ok=True,ignore=shutil.ignore_patterns(".writer.lock"))
    git("add","state",cwd=target)
    git("-c","user.name=NFL lab","-c","user.email=nfl-lab@users.noreply.github.com","commit","-m","Record remote publication timing",cwd=target)
    git("push","origin",f"HEAD:refs/heads/{branch}",cwd=target)
    git("worktree","remove","--force",str(target))
