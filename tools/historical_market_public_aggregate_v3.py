"""Publishable aggregate projection only: no fitting, grading, or selection.

The source is the immutable, independently checked report. One frozen metadata
projection supplies the ATD standalone game's/week's counts missing from that
report; no outcomes, loss arithmetic, raw offers or fitted parameters are read.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ORDER = ["pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "anytime_td", "fantasy_ppr"]
YARDS = {"pass_yd", "rush_yd", "rec_yd", "rush_rec_yd"}
LABELS = {"pass_yd":"Passing yards", "pass_td":"Passing TD", "pass_cmp":"Completions", "pass_att":"Passing attempts",
    "pass_int":"Interceptions", "rush_yd":"Rushing yards", "rush_att":"Carries", "rec":"Receptions", "rec_yd":"Receiving yards",
    "rush_rec_yd":"Combined yards", "anytime_td":"Anytime rush/receive TD", "fantasy_ppr":"Exact PPR"}
POINT_KEYS = {"arm", "rows", "MAE", "MSE", "RMSE", "bias", "close_threshold", "strict_close_rate", "inclusive_close_rate",
    "side_correct_and_strict_close_rate", "side_correct_and_inclusive_close_rate", "point_product_semantics", "paired_vs_F_game", "paired_vs_F_week"}
PROB_KEYS = {"arm", "rows", "Brier", "log_loss", "infinite_log_losses", "probability_semantics", "paired_vs_F_game", "paired_vs_F_week"}


def digest(path):
    path=Path(path);body=path.read_bytes()
    return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}


def member(ref):
    expected={k:ref["container"][k] for k in ["bytes","sha256"]}
    if digest(ref["container"]["path"])!=expected:raise ValueError("frozen aggregate container differs")
    with zipfile.ZipFile(ref["container"]["path"]) as z:body=z.read(ref["member"])
    if len(body)!=ref["bytes"] or hashlib.sha256(body).hexdigest()!=ref["sha256"]:raise ValueError("frozen member differs")
    return body


def standalone_atd_counts(ref):
    import pyarrow.parquet as pq
    # These are metadata counts only. No player ID, actual outcome, line,
    # price, coefficient, model or new probability is decoded by this helper.
    table=pq.read_table(io.BytesIO(member(ref)),columns=["season","week","game_id","target","primary_role","outcome_state","F_probability"])
    frame=table.to_pandas();frame=frame.loc[frame.target.eq("anytime_td") & frame.primary_role & frame.outcome_state.eq("supported_played") & frame.F_probability.notna()]
    return {int(y):{"games":int(g.game_id.nunique()),"weeks":int(g.week.nunique())} for y,g in frame.groupby("season")}


def project(report, terminal, qa, atd, refs):
    source={(c["season"],c["target"]):c for c in report["categories"]}
    coverage={(c["season"],c["target"]):c for c in report["all12_dependency_rows"]}
    years=[]
    for year in [2026,2024]:
        categories=[]
        for target in ORDER:
            c=source.get((year,target));cov=coverage[(year,target)]
            item={"target":target,"category":LABELS[target],"state":cov["state"],"primary_roles":cov["primary_roles"],
                "primary_metric":"MAE" if target in YARDS else "Brier" if target=="anytime_td" else None if target=="fantasy_ppr" else "MSE",
                "primary_metric_units":"yards" if target in YARDS else "dimensionless" if target=="anytime_td" else None if target=="fantasy_ppr" else "counts_squared",
                "all_role_coverage":cov,"point_common_pool":None,"probability_common_pool":None,"football_probability_standalone":None}
            if c:
                item["primary_role_book_offer_incidences"]=c["offered"]
                item["primary_role_supported_unique_player_games"]=c["unique_supported_player_games"]
                item["all_role_outcome_states_book_incidences"]=c["all_offered_outcome_states"]
                points=[{k:v for k,v in r.items() if k in POINT_KEYS} for r in c["point_common_pool"]]
                probs=[{k:v for k,v in r.items() if k in PROB_KEYS} for r in c["probability_common_pool"]]
                standalone=[{k:v for k,v in r.items() if k in PROB_KEYS} for r in c["football_probability_standalone"]]
                if points:
                    arms={r["arm"]:r for r in points};metric=item["primary_metric"]
                    item["point_common_pool"]={"rows":points[0]["rows"],"games":points[0]["paired_vs_F_game"]["clusters"],
                        "weeks":points[0]["paired_vs_F_week"]["clusters"],"metrics":points,
                        "signed_H_minus_baseline_primary_loss":{b:arms["H"][metric]-arms[b][metric] for b in ["F","FC","M"]},
                        "difference_sign":"negative means H has lower loss","H_vs_F_game_interval":arms["H"]["paired_vs_F_game"],
                        "H_vs_F_week_interval":arms["H"]["paired_vs_F_week"],"H_vs_FC_or_M_intervals":"NOT_IN_FIRST_WAVE_REPORT"}
                if probs:
                    item["probability_common_pool"]={"rows":probs[0]["rows"],"games":probs[0]["paired_vs_F_game"]["clusters"],
                        "weeks":probs[0]["paired_vs_F_week"]["clusters"],"metrics":probs}
                if standalone:
                    item["football_probability_standalone"]={"rows":standalone[0]["rows"],"metrics":standalone}
                    if target=="anytime_td":item["football_probability_standalone"].update(atd[year])
                item["F_push_diagnostic"]={k:v for k,v in c["F_push_probability_separate"].items() if k in PROB_KEYS|{"state","rows","other_arms_push_law"}}
            categories.append(item)
        numeric=[c for c in categories if c["point_common_pool"]]
        wins=sum(c["point_common_pool"]["signed_H_minus_baseline_primary_loss"]["F"]<0 for c in numeric)
        years.append({"season":year,"period":"Weeks1–5" if year==2026 else "REG historical outer comparison",
            "numeric_categories":len(numeric),"H_lower_primary_loss_than_aged_F_categories":wins,"categories":categories})
    return {"schema_version":"historical-market-no2025-public-aggregate-v3","status":"INDEPENDENTLY_CHECKED_EXPLORATORY_AGGREGATES_NOT_LIVE_READY",
        "seasons_excluded_from_new_inputs_training_features_labels_selection":[2025],"years":years,
        "method_contract":{"F":"authenticated retained leaf-CDF; counts use law mean/MSE, yards lower median/MAE; 2026 uses frozen2024model trained2019–2023",
            "FC":"football-only earlier calibration: nonnegative-slope L2 empirical point correction; count outputs clamped at zero, signed-yard intercept unbounded; conditional-probability logistic calibration",
            "FS":"separate probability confidence shrink toward0.5, estimated only from2022/2023 available development offers",
            "M":"offering-book-excluded actual named-book point-line heuristic or proportional no-vig decisive probability; no inferred push law",
            "H":"same fixed calibration learner asFC with independentM input added; not a new raw-feature CDF fit",
            "OFFERED_LINE_HEURISTIC":"actual offering-book line scored as a point only; neither a latent-law mean nor a median claim"},
        "cohort_contract":{"point":"same primary-role common cohort forF/FC/M/H/offeredline; one offering book per player-game-category using fixed book priority",
            "probability":"same decisive common cohort forF/FC/FS/M/H; choose book before removing pushes",
            "denominators":"primary_role_book_offer_incidences is primary-role scope; all_role_outcome_states_book_incidences spans ALL roles and counts repeated book offers; do not divide those different populations",
            "dependence":"34,759 player-game-target query rows and92,445 book-threshold incidences are not independent NFL games; different targets/books can share players/games",
            "roles":"original primary roles unchanged; all-role secondary forecasts/coverage are separate and are not primary RB gains for QB props"},
        "uncertainty_limits":["Stored95% paired game/week intervals are nominal exposed-sample bootstrap intervals,500replicates,seed1703,min8clusters; no multiplicity-adjusted qualification",
            "2026 has five weeks: whole-week intervals N_A under the existingmin8routine; this is not a new live-release prerequisite",
            "Only H-versus-F paired intervals are reported here; H-versus-FC/M signed differences have no saved paired interval",
            "2026 passing-yards probability common cohort is only12player-games",
            "Registered error-threshold and bias diagnostics are retained; p90/p95/max error percentiles were not computed in this first-wave aggregate output"],
        "timing_and_scope":{"lane":"timing-unverified exploratory; current-vintage football reconstruction with original explicit seven-day availability assumption",
            "historical_quote_or_publication_proof":False,"historical_SITE_R0_comparator":"UNAVAILABLE: no claimed current-website or historical TopOver/Under win",
            "GAP_SCREENED":"laboratory F point-gap proxy screened using genuine F probability/price; not recorded website TopOver/Under",
            "2026_model_age":"fixed2024CDF trained2019–2023; missing2024training may weaken this control; no best current or forever forecaster claim",
            "calibration":"available2022/2023 only; supplied2022 has no qualifying named-book pairs, so market calibration effectively uses2023; no2024/2026 tuning",
            "ATD":"rush/receive event only; no genuine No quote, so no fairM/H market comparison; zeroTD is loss, neverpush",
            "PPR":"exact label contract and supplied source market absent; unsupported, not zero or a winner",
            "paper":"frozen choices retained; separate zero-fit paper accounting pending; actual book settlement UNQUALIFIED; no ROI/profitability claim",
            "deployment":"no new live model, website feed, scheduler, promotion or scientific qualification"},
        "run":{"resources":terminal["resources"],"whole_wrapper":{"real_seconds":73.93,"user_seconds":68.35,"sys_seconds":6.88,"CPU_seconds_rounded_sum":75.23},
            "actual_base_CDF_fits":0,"actual_tiny_calibration_estimates":144,"real_query_preflight_cells":33,"unique_football_queries":34759,
            "book_threshold_law_incidences":92445,"whole_canonical_book_offer_pool":99388,"context_abstentions":6943,
            "cumulative_retained_bytes_including_failures_and_owners":terminal["cumulative_retained_bytes_including_V1_V2_failures"],
            "write_history":"V1two+V2one+V3two=5; original4cap preserved, one explicit additional technical-retention slot authorized; no budget reset",
            "prior_failures":{"V1":"FAILED strict role-context guard before prediction/fits/losses;30.973CPU30.279wall420950016RSS checkpoint only, full final CPU/RSS unrecorded; original301CPUhard/420wall ceilings retained",
                "V2":"FAILED duplicated player-game model-query guard before prediction/fits/losses; fullwrapper26.40real23.03user3.71sys;373469184RSS is preerror checkpoint, final peak unrecorded"}},
        "independent_verification":{k:qa[k] for k in ["state","checks","primary_point_metric_records","common_probability_metric_records","intervals_recomputed","frozen_original_point_incidence_checks","calibrator_application_value_checks","maximum_calibrator_abs_error","matched_evaluation_rows","all12_dependency_rows","model_loads_fits_new_inference_new_selection_HTTP_filewrites","CPU_seconds","wall_seconds","RSS_peak_bytes"]},
        "verification_references":refs,"privacy":"Only category/season aggregate metrics and non-sensitive verification metadata. No raw quote, player/game record, fitted coefficient, model weight, parameter table or private CSV."}


def fmt(value,digits=4):
    if value is None:return "—"
    if isinstance(value,dict):return value.get("numeric_state","N/A")
    return f"{value:.{digits}f}"


def markdown(data):
    lines=["# No-2025 market comparison — reviewed aggregate checkpoint", "",
        "H lowers the registered primary point loss against the football-only F control in **9 of10numeric categories in both2024and2026**. The2026control is an older frozen model; the2024control uses its corresponding annual model. Independent market and offering-book line heuristics often have lower loss than H. Probability comparisons are mixed; the2026passing-yards probability common pool has only12player-games. These are timing-unverified research results, with no current-website, best-forever, live-readiness or qualification claim.", "",
        "F is the authenticated CDF mean for counts and lower median for yards. In2026it is the frozen2024model trained2019–2023, with2025excluded before lag construction. FC and H are nonnegative-slope L2 empirical point corrections, not stored CDF means/medians; count outputs are clamped at zero while signed-yard intercepts are unbounded. H adds an offering-book-excluded market input to the same learner. FS separately shrinks probability confidence toward0.5. M and L(B) are independent-book and actual offering-book line-as-point heuristics. No numeric point gap creates a probability.", "",
        "Calibration used available2022/2023development offers;2022has no qualifying named-book pairs, so learned market calibration effectively uses2023. Neither2024nor2026was used for calibration/tuning. All quotes remain unqualified for historical timing; football availability uses the explicit original seven-day reconstruction assumption. No authenticated historical SITE/R0 comparator is available.", ""]
    for epoch in data["years"]:
        year=epoch["season"];lines += [f"## {year} — {epoch['period']}", "", "### Primary point comparison", "",
            "Lower is better. **n/g/w** means player-game-category observations / distinct games / weeks on the same primary-role common cohort. Count primary loss is MSE in counts²; it is not a hit percentage. Yard primary loss is MAE in yards.", "",
            "| Category | Primary loss | n/g/w | F | FC | M | H | L(B) |", "|---|---|---:|---:|---:|---:|---:|---:|"]
        for c in epoch["categories"]:
            p=c["point_common_pool"]
            if not p:
                reason="See event probability" if c["target"]=="anytime_td" else "Unsupported exact PPR"
                lines.append(f"| {c['category']} | {reason} | — | — | — | — | — | — |")
                continue
            a={r["arm"]:r for r in p["metrics"]};m=c["primary_metric"];unit="yd" if c["target"] in YARDS else "count²"
            lines.append(f"| {c['category']} | {m} ({unit}) | {p['rows']}/{p['games']}/{p['weeks']} | "+" | ".join(fmt(a[x][m]) for x in ["F","FC","M","H","OFFERED_LINE_HEURISTIC"])+" |")
        lines += ["", "### Signed H contrasts and available uncertainty", "", "Δ=H−baseline in the primary-loss units above; negative favors H. The interval is the stored nominal paired **H−F game**95%interval. Saved H−FC/M intervals are unavailable.", "",
            "| Category | ΔH−F | ΔH−FC | ΔH−M | H−F game95%interval |", "|---|---:|---:|---:|---|"]
        for c in epoch["categories"]:
            p=c["point_common_pool"]
            if not p:continue
            delta=p["signed_H_minus_baseline_primary_loss"];ci=p["H_vs_F_game_interval"]
            interval=f"[{fmt(ci.get('lower95'))}, {fmt(ci.get('upper95'))}]" if "lower95" in ci else ci["state"]
            lines.append(f"| {c['category']} | {delta['F']:+.4f} | {delta['FC']:+.4f} | {delta['M']:+.4f} | {interval} |")
        lines += ["", "### Count MAE — secondary, in counts", "", "Same n/g/w as the point table; these are absolute errors, not exact-hit rates.", "",
            "| Category | F | FC | M | H |", "|---|---:|---:|---:|---:|"]
        for c in epoch["categories"]:
            p=c["point_common_pool"]
            if not p or c["target"] in YARDS:continue
            a={r["arm"]:r for r in p["metrics"]}
            lines.append(f"| {c['category']} | "+" | ".join(fmt(a[x]["MAE"]) for x in ["F","FC","M","H"])+" |")
        lines += ["", "### Probability — Brier loss", "", "Lower is better; ordinary O/U uses the same decisive common cohort for all five arms. ATD uses its separate football-only event cohort because no genuine No quote is available. Log losses and available intervals are retained in PUBLIC_METRICS.json.", "",
            "| Category | n/g/w | F | FC | FS | M | H |", "|---|---:|---:|---:|---:|---:|---:|"]
        for c in epoch["categories"]:
            p=c["probability_common_pool"]
            if not p and c["target"]=="anytime_td":p=c["football_probability_standalone"]
            if not p:
                lines.append(f"| {c['category']} | Unsupported | — | — | — | — | — |")
                continue
            a={r["arm"]:r for r in p["metrics"]}
            lines.append(f"| {c['category']} | {p['rows']}/{p.get('games','—')}/{p.get('weeks','—')} | "+" | ".join(fmt(a[x]["Brier"],6) if x in a else "—" for x in ["F","FC","FS","M","H"])+" |")
        lines += ["", "### Bias and error-threshold diagnostics", "", "Bias is prediction−actual in yards or counts. Close columns show strict/inclusive rates: |error|<10 /≤10yards, or <1/≤1count. These are threshold diagnostics; p90/p95/max-error percentiles were not computed in this first wave. Full F/FC/M/H diagnostics and simultaneous side-correct-and-close rates are in the JSON.", "",
            "| Category | F bias | H bias | F close strict/inclusive | H close strict/inclusive |", "|---|---:|---:|---:|---:|"]
        for c in epoch["categories"]:
            p=c["point_common_pool"]
            if not p:continue
            a={r["arm"]:r for r in p["metrics"]}
            close=lambda r:f"{r['strict_close_rate']:.1%} / {r['inclusive_close_rate']:.1%}"
            lines.append(f"| {c['category']} | {a['F']['bias']:+.4f} | {a['H']['bias']:+.4f} | {close(a['F'])} | {close(a['H'])} |")
        note = "Whole-week intervals are **N/A for2026**: the point cohorts cover five weeks and some probability cohorts cover only four." if year==2026 else "The2024cohorts cover18weeks; saved nominal whole-week intervals are available in the JSON."
        lines += ["", note+" The unchanged minimum-eight-cluster routine is an uncertainty rule, not a new release prerequisite. Results remain exposed-sample research, with no multiplicity-adjusted qualification.", ""]
    lines += ["## Coverage, verification and retained failures", "",
        "The whole canonical pool contains99,388book-offer incidences. Strict source/original-query context checks retain6,943row abstentions with both roles and field reasons. Genuine forecasts cover34,759unique player-game-target queries and92,445book-threshold incidences. Those counts are not independent NFL games. The public JSON separates primary-role offer counts from ALL-role outcome-state book incidences; those denominators must not be mixed. All-role secondary coverage and fallback counts are distinct from primary-role gains.", "",
        "The main run used144small earlier calibration estimates, **zero base CDF fits**,33model loads and no HTTP. Full wrapper time was73.93sreal /68.35suser /6.88ssystem; measured worker peak RSS was646,021,120bytes. Forecasts and choices were durably frozen before outer loss computation. Independent read-only QA passed11,159checks,100point and100common-probability metric records,400paired intervals,53,091original2024frozen-point incidences and312,880calibrator application values, with no new fits, models, predictions or selections.", "",
        "V1 remains FAILED at strict role-context agreement; its30.973CPU/30.279wall/420,950,016RSS figures are pre-preservation checkpoints, not full final resource totals. V2 remains FAILED at duplicated football-query identities; its full wrapper was26.40sreal /23.03suser /3.71ssystem, with final RSS unrecorded. V3 used unique original model queries and unchanged-law fanout to all book thresholds. The original four-write cap was preserved; one separately authorized retention slot made five cumulative writes. All failed evidence remains retained. Cumulative named data plus ownership metadata is17,024,733bytes, below the32MiB/48MiB retained/peak envelope.", "",
        "## Limits and pending paper accounting", "",
        "The aged F control can be weaker than a contemporary football model. Independent M or the actual offering-book line often beats H; the numeric gains do not establish the best current forecaster, a website win, or a forever champion. Passing-yards probability coverage in2026is only12observations. All quote clocks and exact book settlement rules remain unqualified. ATD is only the rushing/receiving event and has no fair market comparison; exact PPR remains unsupported.", "",
        "The frozen GAP_SCREENED policy is a laboratory F point-gap proxy, not historical website TopOver/Under. Paper accounting is **pending a separate zero-fit frozen-row postprocess**. No ROI, profitability, live readiness, promotion or scientific qualification is claimed. No new website feed or scheduler was installed.", "",
        "[Machine-readable permitted aggregates](PUBLIC_METRICS.json) · [Verification references](VERIFICATION_REFS.json)", ""]
    text="\n".join(lines)
    text=re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])|(?<=%)(?=[A-Za-z])"," ",text)
    text=re.sub(r";(?=\w)|(?<=[A-Za-z]),(?=[0-9])",lambda m:m.group()+" ",text)
    text=re.sub(r"\bV ([123])\b",r"V\1",text)
    for old,new in [("sreal","s real"),("suser","s user"),("ssystem","s system"),("p 90","p90"),("p 95","p95"),("L 2","L2"),("R 0","R0"),("TopOver/Under","Top Over/Under"),("**95%","** 95%"),("**,33","**, 33"),(" /68."," / 68."),(" /6."," / 6."),(" /23."," / 23."),(" /3."," / 3."),("CPU/","CPU / "),("wall/","wall / ")]:
        text=text.replace(old,new)
    return text


def assert_public(value):
    banned={"player_id","player_name","game_id","source_row_number","american_odds","d_over","d_under","coef","intercept","weights","leaf_histograms","net_units","selected_rows","parameters"}
    def walk(x):
        if isinstance(x,dict):
            if set(x)&banned:raise ValueError("nonpublic data field in projection")
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(value)
    text=json.dumps(value,sort_keys=True,allow_nan=False)
    if re.search(r"00-[0-9]{7}",text):raise ValueError("GSIS identifier in public aggregate")


def main():
    p=argparse.ArgumentParser();p.add_argument("--terminal",required=True);p.add_argument("--qa",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    terminal=json.loads(Path(a.terminal).read_text());qa=json.loads(Path(a.qa).read_text())
    if terminal["state"]!="COMPLETE_EXPLORATORY_COMPARISON_TECHNICAL_V3" or qa["state"]!="INDEPENDENT_FROZEN_MARKET_NUMERIC_QA_PASS":raise ValueError("actual completed run and independent QA required")
    report_ref=terminal["scores"]["REPORT.json"];report=json.loads(member(report_ref))["report"]
    atd=standalone_atd_counts(terminal["scores"]["MATCHED_SCORES.parquet"])
    refs={"aggregate_report":{"container_bytes":report_ref["container"]["bytes"],"container_sha256":report_ref["container"]["sha256"],"member":report_ref["member"],"bytes":report_ref["bytes"],"sha256":report_ref["sha256"]},
        "forecast_capsule":{k:terminal["bindings"]["FORECASTS_FROZEN.zip"][k] for k in ["bytes","sha256"]},
        "terminal_metadata":digest(a.terminal),"independent_QA_stdout":digest(a.qa),
        "projection":"new aggregate-only allowlist projection; zero fits, models, inference, grading, policy selection or source requests"}
    data=project(report,terminal,qa,atd,refs);assert_public(data)
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    for name,body in {"PUBLIC_METRICS.json":json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+"\n","PUBLIC_RESULTS.md":markdown(data),"VERIFICATION_REFS.json":json.dumps(refs,indent=2,sort_keys=True)+"\n"}.items():
        (output/name).write_text(body)
    print(json.dumps({"state":"PUBLIC_AGGREGATE_PROJECTION_WRITTEN_NOT_PUBLISHED","files":{n:digest(output/n) for n in ["PUBLIC_RESULTS.md","PUBLIC_METRICS.json","VERIFICATION_REFS.json"]},"fits_models_inference_grading_selection_HTTP":0}))


if __name__=="__main__":main()
