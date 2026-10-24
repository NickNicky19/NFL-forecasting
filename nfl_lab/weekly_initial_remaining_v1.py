"""One explicitly registered remaining-W7 bootstrap; metadata override only.

This is not a routine whole-week choice, old12Z retry, new source loader, model
loop, scheduler or publication grant. Numeric execution remains in the shared
generic backend and its unchanged source/model/selector/persistence APIs.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from .state import digest,utc
from . import weekly_generic_producer as generic

VERSION="weekly-initial-remaining-v1"
REGISTRATION=VERSION+"-registration"
REGISTRATION_ID="2026-REG-W07-remaining-15Z-bootstrap-v1"
CUTOFF="2026-10-24T15:00:00Z"
FULL_FIRST="2026-10-23T00:15:00+00:00"
REMAINING_FIRST="2026-10-25T13:30:00+00:00"
ELAPSED=("2026_07_NE_CHI",)
REMAINING=tuple(sorted(("2026_07_PIT_NO","2026_07_SF_ATL","2026_07_CIN_BAL","2026_07_TB_CAR",
    "2026_07_NYG_HOU","2026_07_IND_MIN","2026_07_MIA_NYJ","2026_07_CLE_TEN","2026_07_DEN_ARI",
    "2026_07_GB_DET","2026_07_LA_LV","2026_07_KC_SEA","2026_07_DAL_PHI")))
TARGETS=("pass_yd","pass_td","pass_cmp","pass_att","pass_int","rush_yd","rush_att","rec","rec_yd","rush_rec_yd","anytime_td")
EXPECTED={(t,"LAB_CDF") for t in TARGETS}|{(t,"COUNT_A") for t in ("rush_att","rec")}|{(t,"CATBOOST_MEDIUM") for t in ("pass_yd","rush_yd","rec_yd","rush_rec_yd","anytime_td")}
FIELDS={"schema_version","registration_id","state","registered_at_utc","season","week","season_type","slate_id",
    "slate_kind","full_week_first_kickoff_utc","first_remaining_kickoff_utc","elapsed_game_ids","remaining_game_ids",
    "elapsed_game_count","remaining_game_count","input_cutoff_utc","maximum_uses","build_kind","startup_policy_sha256"}


def validate_registration(registration,*,now):
    r=registration;require=generic.require
    require(set(r)==FIELDS,"closed initial registration schema required")
    require(r["schema_version"]==REGISTRATION and r["registration_id"]==REGISTRATION_ID
        and r["state"]=="FROZEN_ROOT_REGISTERED" and r["maximum_uses"]==1,"one-time root-registered initial bootstrap required")
    require((r["season"],r["week"],r["season_type"],r["slate_id"],r["slate_kind"])
        ==(2026,7,"REG",REGISTRATION_ID,"INITIAL_REMAINING_ONE_TIME"),"exact initial REG W7 identity required")
    require(r["remaining_game_ids"]==list(REMAINING) and r["elapsed_game_ids"]==list(ELAPSED)
        and (r["remaining_game_count"],r["elapsed_game_count"])==(13,1),"literal thirteen remaining/one elapsed games required")
    require(utc(r["full_week_first_kickoff_utc"])==utc(FULL_FIRST)
        and utc(r["first_remaining_kickoff_utc"])==utc(REMAINING_FIRST)
        and r["input_cutoff_utc"]==CUTOFF,"original full-week first and new15Z horizon must remain exact")
    require(r["build_kind"]=="GENUINE_HOSTED_FIXED_BUILD_V1"
        and r["startup_policy_sha256"]=="0ee3eccf4f0e9ed85ee46c6ba4f6df404459fb4f3cabba469bf6dffd9ee2456c","registered startup policy/new genuine build required")
    require(r["registered_at_utc"] is not None and utc(r["registered_at_utc"])<=now<utc(CUTOFF)
        and now<utc(REMAINING_FIRST)-timedelta(hours=6),"actual new registration/choice must precede15Z and remaining-slate deadline")
    return r


def prepare_initial_slate(schedule,registration,registration_ref,*,now):
    r=validate_registration(registration,now=now)
    rows=[s for s in schedule if s["season"]==2026 and s["week"]==7 and s["game_type"]=="REG"]
    generic.require(len(rows)==14 and len({s["game_id"] for s in rows})==14
        and {s["game_id"] for s in rows}==set(REMAINING)|set(ELAPSED),"full original fourteen-game schedule required")
    elapsed=sorted(s["game_id"] for s in rows if utc(s["kickoff_utc"])<=now)
    future=[s for s in rows if utc(s["kickoff_utc"])>now]
    generic.require(elapsed==list(ELAPSED) and sorted(s["game_id"] for s in future)==list(REMAINING)
        and min(utc(s["kickoff_utc"]) for s in rows)==utc(FULL_FIRST)
        and min(utc(s["kickoff_utc"]) for s in future)==utc(REMAINING_FIRST),"honest elapsed/remaining kickoff census differs")
    result=generic.prepare_slate(rows,season=2026,week=7,game_cutoffs={g:CUTOFF for g in REMAINING},now=now)
    result.update(slate_id=REGISTRATION_ID,scheduled_first_kickoff_utc=utc(REMAINING_FIRST).isoformat(),
        weekly_deadline_utc=(utc(REMAINING_FIRST)-timedelta(hours=6)).isoformat(),
        slate_contract=dict(schema_version=VERSION,registration=registration_ref,registered_at_utc=r["registered_at_utc"],
            kind="INITIAL_REMAINING_ONE_TIME",full_week_first_kickoff_utc=utc(FULL_FIRST).isoformat(),
            full_week_deadline_utc=(utc(FULL_FIRST)-timedelta(hours=6)).isoformat(),
            elapsed_game_ids=list(ELAPSED),remaining_game_ids=list(REMAINING),maximum_uses=1,build_kind=r["build_kind"]))
    return result


def validate_plan(plan,*,now):
    from tools.weekly_current_query import pin
    generic.require(plan.get("initial_adapter",{}).get("schema_version")==VERSION,"explicit initial adapter plan required")
    ref=plan["initial_adapter"]["registration"]
    pin(ref)
    registration=json.loads(Path(ref["path"]).read_text())
    validate_registration(registration,now=now)
    generic.require(plan["startup_policy"]["sha256"]==registration["startup_policy_sha256"]
        and plan["slate"]["game_cutoffs"]=={g:CUTOFF for g in REMAINING}
        and plan["slate"].get("slate_contract",{}).get("registration")==ref,"exact registration/policy/new15Z plan binding required")
    generic.require("nfl_lab/weekly_initial_remaining_v1.py" in plan["code_pins"]
        and "tools/weekly_initial_remaining_v1.py" in plan["code_pins"],"adapter and dispatch code must be sealed")
    return registration


def validate_fresh_initial_metadata(registration,model_metadata,receipts,*,now,slot_inventory=None):
    started=utc(registration["registered_at_utc"])
    seen={(m["category"]["target"],m["method_id"]) for m in model_metadata}
    if slot_inventory is None:
        generic.require(len(model_metadata)==18 and seen==EXPECTED,"exact new genuine eighteen-model build metadata required")
    else:
        missing={(r["target"],r["method_id"]) for r in slot_inventory["unavailable"]}
        generic.require(slot_inventory["schema_version"]==generic.SLOT_INVENTORY and seen<=EXPECTED
            and seen|missing==EXPECTED and len(model_metadata)==len(seen),"validated complete initial slot census required")
    for m in model_metadata:
        fit=m["fit_receipt"]
        generic.require(started<=utc(fit["training_source_capture_completed_at"])<=utc(fit["training_started_at"])
            <=utc(fit["training_completed_at"])<=utc(m["artifact_created_at"])<=now,
            "new initial build/source/fit clocks must actually follow registration")
    for name in ("schedules.csv.receipt.json","roster_weekly_2026.parquet.receipt.json","stats_player_week_2026.parquet.receipt.json"):
        generic.require(name in receipts and receipts[name]["status"]=="acquired"
            and started<=utc(receipts[name]["retrieved_utc"])<=now,"fresh initial current-source receipts must follow registration")


class InitialRemainingBackend(generic.ProductionBackend):
    """Override only metadata derivation; inherited run owns the entire pipeline."""
    def consume_registration(self,registration,registration_ref):
        root=Path(self.plan["cache"])/VERSION/"registrations"
        path=root/(REGISTRATION_ID+".json")
        with self.store.transaction():
            generic.require(not path.exists(),"one-time initial registration already consumed; no new namespace retry")
            self.store.register_root(root)
            self.store.atomic_json(path,dict(schema_version=VERSION+"-consumed",registration=registration_ref,
                output_root=self.plan["output_root"],actual_consumed_at=self.clock().isoformat(),maximum_uses=1,
                no_automatic_retry=True,persist_journal_with_private_runtime=True))

    def derive_slate(self,schedule):
        registration=validate_plan(self.plan,now=self.clock())
        ref=self.plan["initial_adapter"]["registration"]
        derived=prepare_initial_slate(schedule,registration,ref,now=self.clock())
        generic.require(derived==self.plan["slate"],"sealed initial metadata differs from actual schedule")
        receipts={Path(r["path"]).name:self.read(r) for r in self.plan["source_bindings"] if r["path"].endswith(".receipt.json")
            and Path(r["path"]).name in {"schedules.csv.receipt.json","roster_weekly_2026.parquet.receipt.json","stats_player_week_2026.parquet.receipt.json"}}
        slots=getattr(self,"slot_inventory",None)
        metadata=slots["original_metadata"] if slots is not None else [self.read(r) for r in self.plan["artifacts"]]
        validate_fresh_initial_metadata(registration,metadata,receipts,now=self.clock(),slot_inventory=slots)
        self.consume_registration(registration,ref)
        return derived
