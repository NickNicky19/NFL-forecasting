"""One sealed future slate through existing source, inference and P2 APIs.

No source, model, selector or transport is invoked on import. Old one-slate
wrappers are deliberately unchanged. Remote persistence/publication are separate
hash-bound consumers of the local result, never inferred from a local write.
"""
from __future__ import annotations

import json
from itertools import product as combinations
from datetime import timedelta
from pathlib import Path

from .state import digest, utc, now_utc

VERSION = "weekly-generic-future-producer-v1"
LIMITS = dict(CPU_seconds=300, wall_seconds=420, RSS_bytes=1073741824,
    address_space_bytes=4294967296, numerical_threads=2, children=0, HTTP=0,
    fits=0, scores=0, invocations=1, retries=0, models=18,
    prediction_rows=18000, selected_rows=5000, new_bytes=16777216,
    global_bytes=536870912)
MODEL_BOUNDARY = "weekly-owner-bootstrap-future-relocation-v1"
EXPORT_BOUNDARY = "weekly-generic-selected-handoff-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare_slate(schedule, *, season, week, game_cutoffs, now):
    """Metadata-only constructor: clocks come from the actual full REG schedule."""
    require(type(season) is int and type(week) is int and 1 <= week <= 18,
            "explicit supported NFL season/REG week required")
    rows = [r for r in schedule if r["season"] == season and r["week"] == week and r["game_type"] == "REG"]
    require(rows and len({r["game_id"] for r in rows}) == len(rows), "unambiguous complete actual week schedule required")
    first = min(utc(r["kickoff_utc"]) for r in rows)
    future = {r["game_id"]: r for r in rows if utc(r["kickoff_utc"]) > now}
    require(set(game_cutoffs) == set(future) and future, "all future games/cutoffs required; no coverage cut")
    require(all(now < utc(game_cutoffs[g]) < utc(r["kickoff_utc"]) for g, r in future.items()),
            "actual future source cutoffs must strictly precede each kickoff")
    return dict(season=season, week=week, season_type="REG", slate_id=f"{season}-REG-W{week:02}-future-v1",
        scheduled_first_kickoff_utc=first.isoformat(), weekly_deadline_utc=(first-timedelta(hours=6)).isoformat(),
        game_cutoffs=dict(game_cutoffs), schedule_identity_sha256=digest(sorted((r["game_id"], utc(r["kickoff_utc"]).isoformat()) for r in rows)),
        scheduled_games=len(rows), elapsed_games=len(rows)-len(future))


def validate_plan(plan, *, now, sealed=True):
    require(plan.get("schema_version") == VERSION and plan.get("budgets") == LIMITS,
            "exact versioned finite future producer required")
    if sealed:
        require(plan.get("state") == "FROZEN_ROOT_REVIEWER_SEALED" and plan.get("execution_authorized") is True
            and plan.get("review", {}).get("status") == "PREEXEC_PASS"
            and plan["review"].get("integrator") == "/root", "preparation is not execution authority")
    s = plan["slate"]
    active = now.year - (now.month < 3)
    require(s["season"] == active and s.get("season_type") == "REG" and 1 <= s["week"] <= 18,
            "actual NFL active season/REG contract required; POST needs a new adapter")
    require(s["game_cutoffs"] and len(s["game_cutoffs"]) <= 16
        and all(now < utc(t) for t in s["game_cutoffs"].values()), "elapsed input cutoffs cannot be backdated/restarted")
    require(plan["source_mode"] == "ADOPT_VERIFIED_CACHE" and plan["HTTP"] == 0,
            "this finite producer adopts authenticated fresh sources; refresh is the existing separate source route")
    require(plan["model_boundary"] == MODEL_BOUNDARY and plan["export_boundary"] == EXPORT_BOUNDARY,
            "explicit restore/export boundaries required")
    require(type(plan["retention_physical_anchor"]) is int and plan["retention_physical_anchor"] >= 0,
            "root must freeze actual cumulative retained bytes including all failures")
    require(plan["history_seasons"]==list(range(2019,active+1))
        and set(plan["allowed_periods"]) == set(map(str, plan["history_seasons"]))
        and all(type(w) is int and 1 <= w <= 18 and (int(y) != active or w < s["week"])
                for y, weeks in plan["allowed_periods"].items() for w in weeks),
            "explicit earlier supported history only; original seven-day gate still applies")
    if not plan.get("frozen_weekly_choice"):
        require(now < utc(s["weekly_deadline_utc"]), "weekly deadline passed without an authenticated frozen choice")
    return plan


def validate_freshness(receipts, *, now, season, limits):
    """Actual retrieval freshness; never a claim of upstream publication."""
    require(set(limits) == {"schedule", "current_roster", "current_statistics", "players"}
        and all(type(n) is int and 0 < n <= 604800 for n in limits.values()), "finite source freshness policy required")
    wanted = {"schedules.csv": "schedule", f"roster_weekly_{season}.parquet": "current_roster",
        f"stats_player_week_{season}.parquet": "current_statistics", "players.parquet": "players"}
    require(set(wanted) <= set(receipts), "complete source receipt census required")
    for name, kind in wanted.items():
        r = receipts[name]
        require(r.get("status") == "acquired" and utc(r["retrieved_utc"]) <= now
            and (now-utc(r["retrieved_utc"])).total_seconds() <= limits[kind],
            "missing/stale/future source receipt; use reference/abstention, never relabel cache as fresh")


def freeze_choices(selector, history, catalog, policy, slate, *, actual_choice_at, prior_choices=()):
    """No current offers/forecasts enter choice. Existing P2 supplies all losses."""
    require(actual_choice_at < utc(slate["weekly_deadline_utc"]), "actual weekly choice must beat the real deadline")
    panel = selector.Panel(history, catalog)
    previous = {}
    for saved in prior_choices:
        d = saved["decision"]
        require(saved["policy"] == "P2" and d["evidence_lane"] == "original_pregame"
            and d["season"] == slate["season"] and d["week"] < slate["week"]
            and utc(d["weekly_decision_cutoff_utc"]) < actual_choice_at
            and saved["catalog_sha256"] == digest(selector.procedure_catalog(catalog)), "unbound previous live P2 choice")
        if d["category"] not in previous or previous[d["category"]]["decision"]["week"] < d["week"]:
            previous[d["category"]] = saved
    choices = []
    for c in policy["categories"]:
        target = c["category"]
        if target == "fantasy_ppr":
            continue
        decision = dict(category=target, season=slate["season"], week=slate["week"], slate_id=slate["slate_id"],
            horizon="player_game", evidence_lane="original_pregame", weekly_decision_cutoff_utc=actual_choice_at.isoformat(),
            slate_first_kickoff_utc=slate["scheduled_first_kickoff_utc"])
        if slate.get("slate_contract") is not None:
            decision["slate_contract"] = slate["slate_contract"]
        old = previous.get(target)
        startup = c["startup_method_id"]
        current = old["members"][0]["method_id"] if old and len(old["members"]) == 1 else startup
        selected = selector.select(panel, decision, "P2", current_id=current)
        if not selected["evidence"].get("scores") and startup == "TD_EQUAL_CDF_CAT" and (not old or len(old["members"]) == 2):
            require(policy["TD_EQUAL_CDF_CAT"]["members"] == {"LAB_CDF": .5, "CATBOOST_MEDIUM": .5}, "registered TD weights required")
            selected.update(state="SELECTED", members=[dict(method_id=m, procedure_version=panel.methods[m]["procedure_version"],
                choice_eligible=panel.procedure_available(m, decision), weight=.5) for m in ("LAB_CDF", "CATBOOST_MEDIUM")])
            selected["evidence"]["registered_startup"] = "TD_HALF_CDF_CAT_COMPONENTS; no aggregate fit clock invented"
        choices.append(selected)
    result=dict(schema_version=VERSION+"-weekly-choice", actual_frozen_at=actual_choice_at.isoformat(),
        weekly_deadline_utc=slate["weekly_deadline_utc"], slate_identity=slate["schedule_identity_sha256"], selections=choices,
        composite_TD_P2_comparison="CAPABILITY_GAP; member-only P2 after common live evidence", policy_sha256=digest(policy))
    if slate.get("slate_contract") is not None:
        result["slate_contract"] = slate["slate_contract"]
    return result


def restore_choices(document, *, slate, catalog, policy, selector, now):
    require(document["schema_version"] == VERSION+"-weekly-choice"
        and document["slate_identity"] == slate["schedule_identity_sha256"]
        and document["weekly_deadline_utc"] == slate["weekly_deadline_utc"]
        and utc(document["actual_frozen_at"]) < utc(slate["weekly_deadline_utc"])
        and utc(document["actual_frozen_at"]) <= now
        and document["policy_sha256"] == digest(policy), "authenticated genuine prior weekly freeze required")
    require(document.get("slate_contract")==slate.get("slate_contract"),"typed slate registration changed after freeze")
    expected={c["category"] for c in policy["categories"] if c["category"]!="fantasy_ppr"}
    require(len(document["selections"])==len(expected)
        and {s["decision"]["category"] for s in document["selections"]}==expected,"complete original weekly choice required")
    for selected in document["selections"]:
        d = selected["decision"]
        require(d["season"] == slate["season"] and d["week"] == slate["week"] and d["slate_id"] == slate["slate_id"]
            and utc(d["weekly_decision_cutoff_utc"]) == utc(document["actual_frozen_at"])
            and selected["catalog_sha256"] == digest(selector.procedure_catalog(catalog)), "weekly procedure/catalog changed after freeze")
    return document


def selected_procedure(selection,code_pins):
    recipe=dict(schema_version=VERSION+"-issued-procedure",members=selection["members"],
        producer_sha256=code_pins["nfl_lab/weekly_generic_producer.py"],selector_sha256=code_pins["nfl_lab/weekly_adaptive.py"])
    if selection["decision"].get("slate_contract") is not None:
        recipe.update(slate_contract=selection["decision"]["slate_contract"],
            adapter_sha256=code_pins["nfl_lab/weekly_initial_remaining_v1.py"])
    return digest(recipe)


def register_selected_versions(choice,records,catalog,code_pins):
    """Metadata-only explicit wrapper/fallback pairs, before current values."""
    result=[]
    for selected in choice["selections"]:
        target=selected["decision"]["category"];reference=catalog["categories"][target]["reference_id"];options=[]
        for member in selected["members"]:
            versions=[(member["method_id"],r["binding"]["sha256"]) for r in records
                if r["manifest"]["category"]["target"]==target and r["manifest"]["method_id"]==member["method_id"]]
            versions.extend((reference,v) for v in catalog["methods"][reference]["model_versions"])
            options.append(list(dict.fromkeys(versions)))
        require(all(len(v)<=16 for v in options),"bounded explicit per-member registration required")
        for versions in combinations(*options):
            require(len(result)<256,"finite wrapper allowlist; no implicit model registration")
            result.append(dict(category=target,method_id="P2_SELECTED",procedure_version=selected_procedure(selected,code_pins),
                model_version=digest([(m,v,c["weight"]) for (m,v),c in zip(versions,selected["members"])])))
    return dict(schema_version=VERSION+"-selected-version-catalog",rows=result,current_values_used=False,
        public_policy_registration="REQUIRED_SEPARATELY; not automatic approval")


def execute(plan, *, backend=None, clock=now_utc, resource_check=lambda: None):
    """Production-callable orchestration; injection is restricted to fictionals."""
    validate_plan(plan, now=clock())
    if backend is None:
        backend = ProductionBackend(plan, clock=clock, resource_check=resource_check)
    elif isinstance(backend,ProductionBackend):
        from .weekly_initial_remaining_v1 import InitialRemainingBackend
        require(type(backend) is InitialRemainingBackend and backend.plan is plan,
                "production uses the explicitly registered initial adapter only")
    else:
        require(getattr(backend, "fictional_only", False) and plan.get("fictional_only") is True, "production uses existing real APIs")
    return backend.run()


class ProductionBackend:
    """Local owned API composition. No token discovery or transport substitution."""
    def __init__(self, plan, *, clock=now_utc, resource_check=lambda: None):
        from .operational_sources import load_source_policy
        from .operational_storage import OperationalStorage
        from tools.weekly_current_query import study_storage_class
        self.plan, self.clock, self.resource_check = plan, clock, resource_check
        self.policy = load_source_policy(plan["source_policy"]["path"])
        require(self.policy["_policy_sha256"]==plan["source_contract"]["source_policy_sha256"],"unchanged original source policy required")
        self.store = study_storage_class(OperationalStorage)(plan["cache"], self.policy, state=plan["state_root"],
            study_anchor=plan["retention_physical_anchor"], study_bytes=LIMITS["new_bytes"])

    def read(self, ref, *, owned=True):
        require(0<ref["bytes"]<=8*1024*1024,"finite eight-MiB metadata/live-evidence input required; never truncate")
        if owned:
            self.auth._verify([ref])
        else:
            from tools.weekly_current_query import pin
            pin(ref)
        return json.loads(Path(ref["path"]).read_text())

    def derive_slate(self,schedule):
        return prepare_slate(schedule,season=self.plan["slate"]["season"],week=self.plan["slate"]["week"],
            game_cutoffs=self.plan["slate"]["game_cutoffs"],now=self.clock())

    def run(self):
        import pandas as pd
        from . import operational_sources as source, weekly_current_query as query, weekly_future_inference as future
        from . import weekly_current_inference as current, weekly_adaptive as selector
        from .owned_reference_batch import validate_owned_references
        from .weekly_source_read_batch import source_read_operation, manifest_bindings
        p, store, clock = self.plan, self.store, self.clock
        with store.transaction():
            require(not Path(p["output_root"]).exists(), "one fresh invocation; failed/partial roots are never retried")
            store._require(LIMITS["new_bytes"])
            output = store.register_root(p["output_root"])
        class Sink(current.BoundedOutput):
            def __init__(self, storage, root, maximum):
                self.storage,self.root,self.maximum,self.unpublished=storage,Path(root),maximum,0
        sink = Sink(store, output, LIMITS["new_bytes"])
        sink.atomic_json(output/"CONSUMED.json", dict(schema_version=VERSION, at=clock().isoformat(), invocations=1, retries=0))
        def write(name, doc):
            sink.atomic_json(output/name, doc)
            return future.binding(output/name)
        def progress():
            self.resource_check()
            require(clock() < min(map(utc, p["slate"]["game_cutoffs"].values())), "source/inference/persistence deadline elapsed")
        fatal=None; result={}; session=None
        try:
            refs=p["owned_inputs"]
            session=future.FutureInferenceSession.from_storage(store)
            self.auth=session
            session._verify(refs)  # Existing operation-local immutable auth; no model load here.
            required=[p[k] for k in ("schedule","roster")]+p["artifacts"]+p["source_bindings"]
            required += [p[k] for k in ("history_bundle","previous_choices","frozen_weekly_choice","reference_forecasts") if p.get(k)]
            require(all(r in refs for r in required), "all source/model/catalog bytes must be sealed owned inputs")
            require(p["schedule"] in p["source_bindings"] and p["roster"] in p["source_bindings"],"same original roster/schedule as source snapshot required")
            catalog=self.read(p["selector_catalog"],owned=False); startup=self.read(p["startup_policy"],owned=False)
            require(startup["schema_version"]=="weekly-provisional-live-policy-v1" and len(p["artifacts"])==18,
                "exact registered startup and eighteen frozen procedures required")
            schedule=pd.read_csv(p["schedule"]["path"], usecols=current.SCHEDULE_COLUMNS)
            calendar=schedule.copy()
            local=pd.to_datetime(calendar.gameday.astype(str)+" "+calendar.gametime.astype(str),errors="coerce")
            calendar["kickoff_utc"]=local.dt.tz_localize("America/New_York",ambiguous="NaT",nonexistent="NaT").dt.tz_convert("UTC")
            derived=self.derive_slate(calendar.to_dict("records"))
            require(derived==p["slate"], "sealed full schedule/clock/slate differs from actual schedule")
            history=self.read(p["history_bundle"]) if p.get("history_bundle") else dict(schema_version=selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[])
            require(all(r.get("evidence_lane")=="original_pregame" for r in history["forecasts"]), "only genuine live evidence may select P2")
            require(all(r["season"]<=derived["season"] and (r["season"]<derived["season"] or r["week"]<derived["week"])
                for r in history["offers"]),"history must exclude current/future target weeks")
            if p.get("frozen_weekly_choice"):
                proof=self.read(p["frozen_weekly_choice"])
                require(proof["schema_version"]==VERSION+"-weekly-choice-completion"
                    and utc(proof["persisted_completed_at"])<utc(derived["weekly_deadline_utc"])
                    and utc(proof["persisted_completed_at"])<=clock(),"genuine predeadline weekly persistence proof required")
                original=self.read(proof["choice_binding"])
                require(utc(original["actual_frozen_at"])<=utc(proof["persisted_completed_at"]),"weekly choice follows its persistence proof")
                choice=restore_choices(original,slate=derived,catalog=catalog,policy=startup,selector=selector,now=clock())
            else:
                choice=freeze_choices(selector,history,catalog,startup,derived,actual_choice_at=clock(),
                    prior_choices=self.read(p["previous_choices"]) if p.get("previous_choices") else ())
            choice_ref=write("WEEKLY_CHOICE.json",choice)  # Before current forecast/source values.
            choice_completed=clock()
            if not p.get("frozen_weekly_choice"):
                require(choice_completed<utc(derived["weekly_deadline_utc"]),"actual weekly decision persistence missed deadline")
            write("WEEKLY_CHOICE_COMPLETION.json",dict(schema_version=VERSION+"-weekly-choice-completion",choice_binding=choice_ref,
                persisted_completed_at=choice_completed.isoformat(),original_predeadline_completion=p.get("frozen_weekly_choice")))
            progress()
            records=[];seen=set()
            for ref in p["artifacts"]:
                m=self.read(ref);key=(m["category"]["target"],m["method_id"])
                require(key not in seen and m["source_contract"]==p["source_contract"]
                    and utc(m["training_cutoff_utc"]).year==derived["season"]
                    and m["procedure_version"]==catalog["methods"][key[1]]["procedure_version"]
                    and ref["sha256"] in catalog["methods"][key[1]]["model_versions"], "frozen model/procedure/source catalog mismatch")
                seen.add(key);records.append(dict(binding=ref,manifest=m,eligible_roles=m["category"]["modeled_roles"]))
            require(seen==current.EXPECTED, "exact eighteen supported frozen slots; no fits/correction reservations")
            version_ref=write("SELECTED_VERSION_CATALOG.json",register_selected_versions(choice,records,catalog,p["code_pins"]))
            require(set(source._names(p["history_seasons"]))=={Path(r["path"]).name for r in p["source_bindings"] if not r["path"].endswith(".receipt.json")},
                "exact finite original raw source/receipt whitelist required")
            for name in source._names(p["history_seasons"]):
                expected=Path(p["source_cache"])/"raw"/name
                require(any(r["path"]==str(expected) for r in p["source_bindings"])
                    and any(r["path"]==str(expected)+".receipt.json" for r in p["source_bindings"]),"all adopted sources must have exact owned bindings")
            source_receipts={name:json.loads((Path(p["source_cache"])/"raw"/(name+".receipt.json")).read_text())
                for name in source._names(p["history_seasons"])}
            validate_freshness(source_receipts,now=clock(),season=derived["season"],limits=p["source_freshness_seconds"])
            asof=clock()
            manifest=source.acquire_operational_history(Path(p["cache"]),p["history_seasons"],self.policy,asof,
                source_cache=Path(p["source_cache"]),allowed_periods=p["allowed_periods"],storage=store)
            validate_freshness(manifest["source_receipts"],now=clock(),season=derived["season"],limits=p["source_freshness_seconds"])
            request=Path(p["cache"])/"operational-source-v2"/self.policy["_policy_sha256"]/"requests"/(source._digest(manifest["request"])+".json")
            refs=manifest_bindings(manifest["namespace"],manifest,manifest_sha256=manifest["manifest_sha256"],
                request_binding=str(request),request_binding_sha256=future.sha(request))
            with source_read_operation(store,refs) as source_receipt:
                prior=source.load_operational_history(Path(p["cache"]),p["history_seasons"],self.policy,asof,allowed_periods=p["allowed_periods"])
            roster=pd.read_parquet(p["roster"]["path"],columns=query.ROSTER_COLUMNS,
                filters=[[("season","==",derived["season"]),("week","==",derived["week"]),("game_type","==","REG")]])
            packet=query.build_current_queries(roster,schedule,season=derived["season"],week=derived["week"],
                cutoff_utc=min(map(utc,derived["game_cutoffs"].values())),maximum_rows=1000,expected_remaining_games=len(derived["game_cutoffs"]))
            packet["queries"]["cutoff_utc"]=packet["queries"].game_id.map(derived["game_cutoffs"]).map(utc)
            features=query.build_shared_features(prior,packet,policy=self.policy,source_contract=p["source_contract"])
            del prior
            queries=packet["queries"]
            for key in ("queries","quarantine","no_remaining_game"):
                store.write_dataframe(packet[key],output/(key+".parquet"),index=False)
            qref=future.binding(output/"queries.parquet")
            fref,cref=future.persist_feature_capture(output/"features.parquet",features,
                features=[n for n in features if n.startswith("f_")],source_contract=p["source_contract"],
                source_bindings=p["source_bindings"],storage=sink)
            # This parameterized bridge reuses unchanged canonical ID validators.
            bridge=exact_bridge(queries,schedule,schedule_binding=p["schedule"],query_binding=qref,season=derived["season"],week=derived["week"])
            bref=write("IDENTITY_BRIDGE.json",dict(schema_version=VERSION+"-identity",identities=list(bridge.values()),visible_board_match="NOT_YET_CHECKED",name_matching=False))
            write("SOURCE.json",dict(manifest_sha256=manifest["manifest_sha256"],source_read=source_receipt,population=packet["coverage"],
                actual_completed_at=clock().isoformat(),freshness=p["source_freshness_seconds"],upstream_publication="NOT_INFERRED"))
            progress()
            session.prepare(p["artifacts"])
            capture_doc=self.read(cref)
            captures,all_rows=capture(session,records,features,bridge,choice,cref,capture_doc,sink,output,p,clock,progress)
            captures.update(schema_version=VERSION+"-candidate-capture",state="GENERIC_CANDIDATE_FORECASTS_PERSISTED",
                actual_completed_at=clock().isoformat(),shared_features=fref,original_feature_capture=cref,
                procedure_catalog=p["selector_catalog"],source_population=packet["coverage"],remote_durability="NOT_ESTABLISHED")
            candidate_ref=write("CANDIDATES.json",captures)
            # Current values enter only after the immutable weekly choice.
            bundle=dict(history)
            bundle["offers"]=[*history["offers"],*offers(queries,records,derived)]
            reference=self.read(p["reference_forecasts"]) if p.get("reference_forecasts") else []
            require(all(r["method_id"] in {"R0","RAW"} and r["evidence_lane"]=="original_pregame" for r in reference),"authentic current reference controls only")
            offered_ids={r["offered_id"] for r in bundle["offers"]}
            bundle["forecasts"]=[*history["forecasts"],*[r for r in all_rows if r["offered_id"] in offered_ids],
                *[r for r in reference if r["offered_id"] in offered_ids]]
            bundle["decisions"]=[*history["decisions"],*[s["decision"] for s in choice["selections"]]]
            panel=selector.Panel(bundle,catalog);selected=[]
            for selected_choice in choice["selections"]:
                progress()
                for row in selector.issue(panel,selected_choice):
                    stamp=clock();require(len(selected)<LIMITS["selected_rows"],"selected row ceiling; no truncation")
                    require(stamp<utc(row["cutoff_utc"]) and all(utc(c["provenance"]["issued_at"])<=stamp for c in row["components"]),
                        "actual selected issuance must follow components and precede its own source cutoff")
                    identity=bridge[(row["season"],row["week"],row["game_id"],row["player_id"])]
                    row.update(identity,issued_at=stamp.isoformat(),source_cutoff_utc=row["cutoff_utc"],
                        method_id="P2_SELECTED",procedure_version=selected_procedure(selected_choice,p["code_pins"]),
                        model_version=digest([(c["method_id"],c["model_version"],c["weight"]) for c in row["components"]]),
                        decision_binding=choice_ref,primary_role=True,public_initial_scope_eligible=row["forecast_value"] is not None,
                        source_policy_sha256=p["source_contract"]["source_policy_sha256"],query_source_sha256=qref["sha256"],
                        source_capture_completed_at=capture_doc["feature_persist_completed_at"],
                        historical_feature_availability_uncertain=True,historical_feature_availability_rule=p["source_contract"]["availability_rule"],
                        operational_eligible=row["forecast_value"] is not None,scientific_qualification=False,public_export_authorized=False)
                    for component in row["components"]:
                        original=panel.forecasts[(row["offered_id"],component["method_id"])]
                        component["source_projection_receipt"]=original.get("source_projection_receipt")
                        component["source_projection_receipt_completed_at"]=original.get("source_projection_receipt_completed_at")
                    if derived.get("slate_contract") is not None:
                        row["slate_contract"]=derived["slate_contract"]
                    selected.append(row)
            selected_receipt=future.persist_policy_inputs(output/"selected.jsonl.gz",[selected],storage=sink,
                max_serialized_bytes=4*1024*1024,clock=clock)
            selected_completed=clock()
            output_refs=[choice_ref,candidate_ref,bref,fref,cref,selected_receipt["binding"],future.binding(output/"selected.jsonl.completion.json")]
            for item in captures["models"]:
                ref=item["persistence"]["binding"]
                output_refs.extend([ref,future.binding(Path(ref["path"]).with_suffix(".completion.json"))])
            session._verify(output_refs)
            progress()
            result=dict(state="PARTIAL_FUTURE_SLATE_RETAINED" if any(s["failure"] for s in captures["models"]) else "LOCAL_FUTURE_SLATE_CAPTURED",weekly_choice=choice_ref,selected=selected_receipt,bridge=bref,
                decision=choice_ref,parent_capture=candidate_ref,startup_policy=p["startup_policy"],
                selected_version_catalog=version_ref,
                decision_persist_completed_at=choice_completed.isoformat(),selected_body_and_receipt_persist_completed_at=selected_completed.isoformat(),
                features=fref,feature_capture=cref,candidate_capture=captures,source_population=packet["coverage"],
                local_readback="SAME_PROCESS_OWNED_IMMUTABLE_READBACK",output_refs=output_refs,
                export_boundary=EXPORT_BOUNDARY,remote_durability="NOT_ESTABLISHED",independent_remote_restore="REQUIRED_BEFORE_PUBLIC_USE",
                public_export_authorized=False,website_activation=False,scientifically_qualified=False)
            if derived.get("slate_contract") is not None:
                result["slate_contract"]=derived["slate_contract"]
        except BaseException as error:
            fatal=dict(type=type(error).__name__,reason=str(error)[:500])
        finally:
            if session is not None:
                try:session.close()
                except BaseException as error:fatal=fatal or dict(type=type(error).__name__,reason=str(error)[:500])
        result.update(schema_version=VERSION,fatal=fatal,state="FAILED_RETAINED" if fatal else result["state"],
            actual_completed_at=clock().isoformat(),all_failed_bytes_retained=True,HTTP=0,fits=0,scores=0)
        write("FINISHED.json",result)
        if not fatal:
            try:
                progress()
                write("EXPORT_INPUTS.json",dict(schema_version=EXPORT_BOUNDARY,source_state=result["state"],
                    terminal=future.binding(output/"FINISHED.json"),selected=selected_receipt["binding"],
                    completion=future.binding(output/"selected.jsonl.completion.json"),decision=choice_ref,parent_capture=candidate_ref,
                    bridge=bref,startup_policy=p["startup_policy"],procedure_catalog=p["selector_catalog"],
                    selected_version_catalog=version_ref,
                    decision_persist_completed_at=choice_completed.isoformat(),selected_body_and_receipt_persist_completed_at=selected_completed.isoformat(),
                    producer_terminal_completed_at=clock().isoformat(),rights=None,durability=None,R0=None,
                    public_export_authorized=False,external_witnesses_required=True))
            except BaseException as error:
                # Immutable local-capture terminal stays true; export is a separate failed stage.
                result["state"]="LOCAL_CAPTURE_RETAINED_EXPORT_HANDOFF_FAILED"
                result["handoff_failure"]=dict(type=type(error).__name__,reason=str(error)[:240])
                try:write("EXPORT_FAILURE.json",result["handoff_failure"])
                except BaseException:result["failure_receipt_write_failed"]=True
        return result


def exact_bridge(queries,schedule,*,schedule_binding,query_binding,season,week):
    """Generic counterpart of the initial bridge; exact source namespaces only."""
    from . import weekly_current_query as q
    from . import data
    import pandas as pd
    games=schedule.loc[schedule.season.eq(season)&schedule.week.eq(week)&schedule.game_type.eq("REG")].copy()
    require(not games.game_id.duplicated().any() and "espn" in games,"exact original schedule ESPN identities required")
    local=pd.to_datetime(games.gameday.astype(str)+" "+games.gametime.astype(str),errors="coerce")
    games["kickoff_utc"]=local.dt.tz_localize("America/New_York",ambiguous="NaT",nonexistent="NaT").dt.tz_convert("UTC")
    games["website_game_id"]=games.espn.map(q._sleeper)
    require(games.website_game_id.notna().all() and not games.website_game_id.duplicated().any(),"unambiguous ESPN bridge required")
    for name in ("home_team","away_team"):
        games[name]=data._team(games[name])
    index=games.set_index("game_id");result={}
    for r in queries.to_dict("records"):
        require(q._gsis(r["player_id"])==r["player_id"] and q._sleeper(r["sleeper_id"])==r["sleeper_id"],"canonical source IDs required")
        g=index.loc[r["game_id"]];sides={g.home_team:g.away_team,g.away_team:g.home_team}
        require(sides.get(r["team"])==r["opponent"] and utc(g.kickoff_utc)==utc(r["kickoff_utc"]),"exact team/game/kickoff bridge differs")
        item=dict(gsis_id=r["player_id"],gsis_game_id=r["game_id"],sleeper_id=r["sleeper_id"],website_player_id=r["sleeper_id"],
            website_game_id=g.website_game_id,team=r["team"],opponent=r["opponent"],kickoff_utc=utc(r["kickoff_utc"]).isoformat(),
            query_source_sha256=query_binding["sha256"],schedule_source_sha256=schedule_binding["sha256"],
            identity_bridge_kind="EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES",actual_visible_board_compatibility="NOT_YET_CHECKED")
        item["identity_binding_sha256"]=digest(item)
        result[(r["season"],r["week"],r["game_id"],r["player_id"])]=item
    return result


def offers(queries,records,slate):
    categories={r["manifest"]["category"]["target"]:r["manifest"]["category"] for r in records};result=[]
    for target,c in categories.items():
        for r in queries.loc[queries.position.isin(c["primary_roles"])].to_dict("records"):
            identity={k:r[k] for k in ("season","week","game_id","player_id")};identity["category"]=target
            result.append(dict(identity,offered_id=digest(identity),slate_id=slate["slate_id"],horizon="player_game",
                position=r["position"],team=r["team"],opponent=r["opponent"],
                kickoff_utc=utc(r["kickoff_utc"]).isoformat(),cutoff_utc=utc(r["cutoff_utc"]).isoformat()))
    return result


def capture(session,records,features,bridge,choice,capture_ref,capture_doc,sink,output,plan,clock,progress):
    """Small parameterized wrapper; predictors/persistence are unchanged APIs."""
    from . import weekly_current_inference as current, weekly_future_inference as future
    projections={};groups=[];rows=[];statuses=[];charged=0
    choice_clock=choice["actual_frozen_at"]
    for ordinal,(cutoff,frame) in enumerate(features.groupby("cutoff_utc",sort=False)):
        views,keys=current.projection_receipts(records,frame,capture_doc,capture_ref,storage=sink,output=Path(output)/f"views/{ordinal}",clock=clock)
        groups.append((cutoff,views,keys))
        projections.update({v["binding"]["path"]:v["binding"] for v in views.values()})
    session._verify(list(projections.values()))  # One owned batch, then immutable operation-local identities.
    for record in records:
        m=record["manifest"];version=record["binding"]["sha256"];expected=[];observed=[];failure=None
        for _,views,keys in groups:
            expected.extend(digest({**{k:r[k] for k in ("season","week","game_id","player_id")},"category":m["category"]["target"]})
                for r in views[keys[version]]["view"].to_dict("records"))
        def chunks():
            nonlocal charged,failure
            try:
                for cutoff,views,keys in groups:
                    view=views[keys[version]]
                    for chunk in session.predict_chunks(version,view["view"],context=dict(cutoff_utc=utc(cutoff).isoformat(),
                        weekly_decision_cutoff_utc=choice_clock,slate_id=plan["slate"]["slate_id"],source_contract=plan["source_contract"],
                        evidence_lane="original_pregame",reference_stream="candidate",query_source_sha256=capture_doc["feature_binding"]["sha256"],
                        feature_capture_receipt=view["binding"]),clock=clock,batch_size=128):
                        progress();require(charged+len(chunk)<=LIMITS["prediction_rows"],"all-model row ceiling; never truncate")
                        for row in chunk:
                            require(row["offered_id"]==expected[len(observed)],"offered identity/order lost")
                            require(utc(view["ready_at"])<=utc(row["issued_at"]),"projection descriptor follows issuance")
                            row.update(bridge[(row["season"],row["week"],row["game_id"],row["player_id"])],
                                source_cutoff_utc=row["cutoff_utc"],source_projection_receipt=view["binding"],
                                source_projection_receipt_completed_at=view["ready_at"],participation_state="unknown",
                                primary_role=row["position"] in m["category"]["primary_roles"],
                                public_initial_scope_eligible=bool(row["operational_eligible"] and row["position"] in m["category"]["primary_roles"]),
                                capture_registration_id=VERSION,historical_feature_availability_uncertain=True,
                                upstream_publication="NOT_INFERRED_FROM_CURRENT_READBACK")
                            if plan["slate"].get("slate_contract") is not None:
                                row["slate_contract"]=plan["slate"]["slate_contract"]
                            observed.append(row["offered_id"])
                        charged+=len(chunk);rows.extend(chunk);yield chunk
            except Exception as error:failure=dict(type=type(error).__name__,reason=str(error)[:300])
        progress()
        receipt=future.persist_policy_inputs(Path(output)/"candidates"/m["category"]["target"]/(m["method_id"]+".jsonl.gz"),chunks(),
            storage=sink,max_serialized_bytes=4*1024*1024,clock=clock)
        require(receipt["rows"]==len(observed),"persisted prefix differs from observed prefix")
        status=dict(target=m["category"]["target"],method_id=m["method_id"],artifact=record["binding"],persistence=receipt,
            expected_rows=len(expected),issued_rows=len(observed),unissued_offered_ids=expected[len(observed):],failure=failure,
            state="FAILED_RETAINED" if failure else "CAPTURED")
        sink.atomic_json(Path(output)/"model-status"/(m["category"]["target"]+"-"+m["method_id"]+".json"),status)
        statuses.append(status)
    return dict(models=statuses,prediction_rows=charged,all_offered_rows_retained=True),rows
