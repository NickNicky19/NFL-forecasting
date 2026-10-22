"""One daily writer cadence with DST and delayed-schedule decisions."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo


def decision(event:str,mode:str|None=None,now:datetime|None=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("aware cadence clock required")
    local=now.astimezone(ZoneInfo("America/Chicago"))
    scheduled=event=="schedule"
    due=not scheduled or (local.hour==8 and 36<=local.minute<=56)
    chosen=mode or ("grade" if scheduled and not due else "train" if scheduled and local.weekday()==6 else "daily")
    if chosen not in ["daily","train","replay","grade"]:raise ValueError("unknown cadence mode")
    return {"observed_chicago":local.isoformat(),"due":due,"mode":chosen,
            "pregame_issuance_allowed":bool(due and chosen in ["daily","train"]),
            "reason":"DUE" if due else "MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED"}
