from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

from nfl_lab.state import capture,save


def run(*args,cwd,env=None):
    return subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True,check=True).stdout


def test_actual_local_remote_handover_retry_and_health_only(tmp_path):
    source=Path(__file__).resolve().parents[1]
    remote=tmp_path/"remote.git";repo=tmp_path/"repo";repo.mkdir()
    run("git","init","--bare",str(remote),cwd=tmp_path)
    run("git","init","-b","main",cwd=repo)
    (repo/"config").mkdir();(repo/"config/research.json").write_text("{}")
    (repo/".gitignore").write_text("state/\n")
    run("git","add",".",cwd=repo)
    run("git","-c","user.name=test","-c","user.email=test@example.invalid","commit","-m","initial",cwd=repo)
    run("git","remote","add","origin",str(remote),cwd=repo)
    run("git","push","origin","main",cwd=repo)
    now=datetime.now(timezone.utc)
    row=dict(player_id="p",game_id="g",team="A",opponent="B",target="rec",model_id="m",scoring_id="v1",input_sha256="a"*64,code_sha256="b"*64,kickoff_utc=(now+timedelta(days=1)).isoformat(),mean=1)
    capture(repo/"state",[row])
    env={**os.environ,"PYTHONPATH":str(source),"PYTHONDONTWRITEBYTECODE":"1"}
    script=str(source/"tools/persist_state.py")
    run(sys.executable,script,cwd=repo,env=env)
    tree=run("git","ls-tree","--name-only","-r","lab-state",cwd=remote)
    assert "state/forecasts/" in tree and "state/publication/" in tree
    assert ".writer.lock" not in tree and "config/research.json" not in tree
    before=run("git","rev-parse","lab-state",cwd=remote)
    save(repo/"state","health",{"health":"updated"})
    run(sys.executable,script,cwd=repo,env=env)
    assert run("git","rev-parse","lab-state",cwd=remote)!=before
    before=run("git","rev-parse","lab-state",cwd=remote)
    run(sys.executable,script,cwd=repo,env=env)
    assert run("git","rev-parse","lab-state",cwd=remote)==before
    assert run("git","worktree","list","--porcelain",cwd=repo).count("worktree ")==1
