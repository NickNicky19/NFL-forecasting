"""One daily writer cadence with DST and delayed-schedule decisions."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo

LEGACY_POLICY = "legacy-0836-v1"
PARENT_POLICY = "audit-weekly-parent-0736-v1"
SINGLE_WORKFLOW_CRON = "36 12,13,14 * * *"


def decision(event:str,mode:str|None=None,now:datetime|None=None,*,policy:str=LEGACY_POLICY):
    if policy not in {LEGACY_POLICY,PARENT_POLICY}:raise ValueError("unknown cadence policy")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("aware cadence clock required")
    local=now.astimezone(ZoneInfo("America/Chicago"))
    scheduled=event=="schedule"
    hour=8 if policy==LEGACY_POLICY else 7
    due=not scheduled or (local.hour==hour and 36<=local.minute<=56)
    chosen=mode or ("grade" if scheduled and not due else "train" if policy==LEGACY_POLICY and scheduled and local.weekday()==6 else "daily")
    if chosen not in ["daily","train","replay","grade"]:raise ValueError("unknown cadence mode")
    if policy==PARENT_POLICY and chosen=="train":raise ValueError("parent cadence never selects training")
    result={"observed_chicago":local.isoformat(),"due":due,"mode":chosen,
            "pregame_issuance_allowed":bool(due and chosen in ["daily","train"]),
            "reason":"DUE" if due else "MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED"}
    if policy==PARENT_POLICY:result["policy_version"]=PARENT_POLICY
    return result
