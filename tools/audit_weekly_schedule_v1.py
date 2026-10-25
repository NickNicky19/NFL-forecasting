"""Existing-lab schedule preparation; dispatch requires sealed real readiness."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout,redirect_stderr
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


def main(argv=None,*,environ=None,transport=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("template","plan","dispatch"));parser.add_argument("--execute",action="store_true")
    parser.add_argument("--registration",type=Path);parser.add_argument("--registration-sha256")
    parser.add_argument("--schedule",type=Path);parser.add_argument("--season",type=int);parser.add_argument("--week",type=int)
    parser.add_argument("--output",type=Path);parser.add_argument("--intent",type=Path)
    args=parser.parse_args(argv)
    if args.phase=="dispatch" and not args.execute:
        print('{"state":"SCHEDULE_PREPARATION_ONLY_NO_IO","dispatches":0}');return 2
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    try:
        if args.execute:
            resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512 << 20,512 << 20))
            signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
        from nfl_lab import audit_weekly_schedule_v1 as schedule
        schedule.require(not args.execute or args.phase=="dispatch","ONLY_REGISTERED_DISPATCH_CAN_EXECUTE")
        if args.phase=="template":
            schedule.require(args.output is not None,"SCHEDULE_TEMPLATE_OUTPUT_REQUIRED")
            result=schedule.write_once(args.output,schedule.template(root))
            print(json.dumps(dict(state="UNAPPROVED_SCHEDULE_TEMPLATE",sha256=result["sha256"],dispatches=0),sort_keys=True));return 0
        rows=schedule.decode(schedule.read(args.schedule,512 << 10))
        if args.phase=="plan":
            schedule.require(args.output is not None,"PRIVATE_SCHEDULE_PLAN_OUTPUT_REQUIRED")
            proposal=schedule.plan(rows,season=args.season,week=args.week,at=schedule.now())
            metadata=dict(plan=proposal,horizon_proposal=schedule.horizon_proposal(rows,season=args.season,week=args.week))
            result=schedule.write_once(args.output,metadata)
            print(json.dumps(dict(state=proposal["state"],sha256=result["sha256"],dispatches=0,exact_horizons_guaranteed=False),sort_keys=True));return 0
        env=os.environ if environ is None else environ
        schedule.require(args.registration is not None and args.registration_sha256 is not None and args.intent is not None,
            "SEALED_SCHEDULE_INPUT_AND_DURABLE_INTENT_REQUIRED")
        raw=schedule.read(args.registration);p=schedule.decode(raw)
        schedule.require(raw==schedule.canonical(p) and schedule.sha(raw)==args.registration_sha256
            ==env.get("AUDIT_WEEKLY_SCHEDULE_REGISTRATION_SHA256"),"EXACT_PARENT_SEALED_OPERATIONAL_REGISTRATION_HASH")
        schedule.registration(p,root)
        runner=Path(env["RUNNER_TEMP"]).absolute()
        schedule.require(args.intent.is_absolute() and args.intent.is_relative_to(runner),"PRIVATE_CURRENT_RUN_DISPATCH_INTENT_REQUIRED")
        # Only the execute path reads the actual automatic token. No gh/key or
        # local credential fallback exists. Callback loading follows API auth.
        api=schedule.Client(env.get("GITHUB_TOKEN"),transport=transport)
        def callback(*values,**kwargs):return schedule.load_callback(p,root)(*values,**kwargs)
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            result=schedule.dispatch(p,rows,season=args.season,week=args.week,api=api,env=env,root=root,intent_path=args.intent,metadata_callback=callback)
        print(json.dumps(result,sort_keys=True));return 0 if result["state"]!="DISPATCH_UNRESOLVED_NO_RETRY" else 1
    except Exception as error:
        from nfl_lab import audit_weekly_schedule_v1 as schedule
        code=str(error) if isinstance(error,schedule.ScheduleError) else "SCHEDULE_OPERATION_GUARD"
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code) is None:code="SCHEDULE_OPERATION_GUARD"
        print(json.dumps(dict(state="SCHEDULE_BLOCKED_OR_UNRESOLVED",reason=code,dispatches_unknown=True),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
