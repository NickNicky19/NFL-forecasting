"""Render existing aggregate comparisons; no model, source, or row-table access."""
import argparse
import hashlib
import json
from pathlib import Path


def bound(path, expected):
    body = Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("finished aggregate binding changed")
    return json.loads(body)


def main():
    parser = argparse.ArgumentParser()
    for key in ("report", "report-sha256", "completion", "completion-sha256",
                "original-completion", "original-completion-sha256", "output"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    final = bound(args.report, args.report_sha256)
    outer = bound(args.completion, args.completion_sha256)
    original = bound(args.original_completion, args.original_completion_sha256)
    if (outer["state"] != "COMPLETED" or original["state"] != "FAILED"
            or final["new_fits_predictions_law_calls_source_label_reads_HTTP"] != 0
            or final["original_completion_sha256"] != args.original_completion_sha256):
        raise ValueError("completed reporting continuation and original failure required")
    report = final["report"]
    if (len(report["targets"]) != 12 or report["historical_SITE"] != "UNAVAILABLE"
            or report["historical_raw_Sleeper"] != "UNAVAILABLE"
            or report["evidence"] != "EXPOSED_SOURCE_MATCHED_DEVELOPMENT"):
        raise ValueError("unchanged evidence lane and all twelve targets required")
    public = dict(
        study="direct-booster-screen-v1-20261023",
        reporting_version="direct-booster-report-recovery-v1-20261023",
        evidence=report["evidence"], original_run_state="FAILED",
        historical_SITE="UNAVAILABLE", historical_raw_Sleeper="UNAVAILABLE",
        promotion="NONE", release_ready=False,
        aggregate_report_SHA256=args.report_sha256,
        original_completion_SHA256=args.original_completion_sha256,
        reporting_completion_SHA256=args.completion_sha256,
        original_resource_accounting=final["original_resource_accounting"],
        original_supervisor_receipt=original, reporting_supervisor_receipt=outer,
        slots=[{k: slot[k] for k in ("year", "target", "method", "library", "complexity",
                "state", "fit_state", "rows", "reason") if k in slot} for slot in report["slots"]],
        targets=report["targets"])
    matrix = []
    lines = ["# Six direct booster pipelines: exposed historical development", "",
        "Same permitted features, populations and cutoffs as the source-matched controls.",
        "Historical raw Sleeper and SITE forecasts are unavailable for this panel.",
        "Positive improvement means lower error; it is not a change in hit rate.",
        "The displayed minimum is selected from this screen, not independent confirmation.", "",
        "| Target | Primary loss | Paired n / games / weeks | Lowest new loss (method) | CDF loss | Change vs CDF | Change vs role B |",
        "|---|---|---|---|---|---|---|"]
    def number(value):
        return "N/A" if value is None else f"{value:.6f}"
    def percent(value):
        return "N/A" if value is None else f"{value:+.2f}%"
    for target, item in report["targets"].items():
        if "pairs" not in item:
            matrix.append(dict(target=target, state=item["state"], release_ready=False))
            lines.append(f"| {target} | Blocked exact labels | 0 | N/A | N/A | N/A | N/A |")
            continue
        pairs = [p for p in item["pairs"] if p["population"] == "primary_roles"
                 and p["period"] == "pooled_2022_2024"]
        cdf = [p for p in pairs if p["comparator"] == "leaf_cdf"
               and p["completion"] == "COMPLETE_REQUIRED_YEARS" and p["candidate_loss"] is not None]
        if not cdf:
            raise ValueError("missing complete development cells")
        best = min(cdf, key=lambda p: (p["candidate_loss"], p["candidate"]))
        role = next(p for p in pairs if p["candidate"] == best["candidate"] and p["comparator"] == "role_B")
        nominee = next(p for p in item["research_nominations"] if p["method"] == best["candidate"])
        matrix.append(dict(target=target, state="EXPOSED_DEVELOPMENT_ONLY",
            displayed_selection="Lowest primary loss among this screen's complete methods; selection-exposed",
            primary_metric=item["primary_metric"], selected_method=best["candidate"],
            CDF_pair=best, role_B_pair=role, research_nomination=nominee,
            all_research_nominations=item["research_nominations"],
            historical_SITE="UNAVAILABLE", historical_raw_Sleeper="UNAVAILABLE", release_ready=False))
        n = f"{best['paired_rows']} / {best['games']} / {best['weeks']}"
        lines.append(f"| {target} | {item['primary_metric']} | {n} | {number(best['candidate_loss'])} ({best['candidate']}) | {number(best['control_loss'])} | {percent(best['improvement_pct'])} | {percent(role['improvement_pct'])} |")
    lines += ["", "## All settings, including adverse results", "",
        "Each row is pooled primary-role development on the exact paired cohort.",
        "Count means use MSE and the CDF mean; signed-yard points use MAE and the CDF median; TD uses Brier.",
        "The full JSON preserves annual/all-offered comparisons, secondary errors, bias, tails, fallback coverage, nominal uncertainty and every nomination failure.", "",
        "| Target | Method | Candidate primary | CDF primary | Change vs CDF | Change vs role B | Research nomination |",
        "|---|---|---|---|---|---|---|"]
    for target, item in report["targets"].items():
        if "pairs" not in item:
            continue
        pairs = [p for p in item["pairs"] if p["population"] == "primary_roles" and p["period"] == "pooled_2022_2024"]
        for pair in [p for p in pairs if p["comparator"] == "leaf_cdf"]:
            role = next(p for p in pairs if p["candidate"] == pair["candidate"] and p["comparator"] == "role_B")
            nomination = next(p for p in item["research_nominations"] if p["method"] == pair["candidate"])
            lines.append(f"| {target} | {pair['candidate']} | {number(pair['candidate_loss'])} | {number(pair['control_loss'])} | {percent(pair['improvement_pct'])} | {percent(role['improvement_pct'])} | {nomination['decision']} |")
    output = Path(args.output)
    if output.exists():
        raise ValueError("fresh public aggregate directory required")
    output.mkdir(parents=True)
    for name, value in (("aggregate-report.json", public), ("category-status.json", matrix)):
        (output / name).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    (output / "aggregate-report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"targets": len(matrix), "public_files": 3, "new_fits_predictions_scores": 0,
        "original_failed": True, "release_ready": False}))


if __name__ == "__main__":
    main()
