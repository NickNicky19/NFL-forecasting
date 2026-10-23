"""Fictional seals, byte aliases, scoring order and complete package matrix."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nfl_lab.role_boosting_campaign as campaign
from nfl_lab.cdf_engine import KEYS
from nfl_lab.median_boosting import score_frozen_rows
from nfl_lab.role_boosting import DESIGN, VERSION, package_kind
from test_cdf_engine import fictional


def frozen_fixture():
    _, query, category = fictional()
    frozen = query[KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]].copy()
    frozen["target"], frozen["method"], frozen["point"] = category["target"], "fictional_frozen", 3.
    frozen["probability"], frozen["actual"] = np.nan, np.nan
    frozen["participation_state"], frozen["outcome_state"] = "unread", "unread"
    frozen["primary_role"], frozen["history_state"], frozen["fallback"] = True, "warm", ""
    return query, frozen, category


def test_byte_alias_identical_and_strict_unread_context(tmp_path):
    query, frozen, category = frozen_fixture()
    source = tmp_path / "old.parquet"
    frozen.to_parquet(source, index=False)
    binding = {"path": str(source), "sha256": campaign.digest(source)}
    campaign.byte_copy(binding, tmp_path / "alias.parquet")
    assert source.read_bytes() == (tmp_path / "alias.parquet").read_bytes()
    campaign.verify_frozen(frozen, query, category)
    bad = frozen.copy()
    bad.loc[bad.index[0], "actual"] = 1.
    with pytest.raises(ValueError, match="unread"):
        campaign.verify_frozen(bad, query, category)
    bad = frozen.copy()
    bad.loc[bad.index[0], "team"] = "fictional-wrong"
    with pytest.raises(ValueError, match="context"):
        campaign.verify_frozen(bad, query, category)
    with pytest.raises(ValueError, match="destination exists"):
        campaign.byte_copy(binding, tmp_path / "alias.parquet")


def test_alias_packages_make_no_fit_or_predict_calls_and_retain_exact_bytes(tmp_path, monkeypatch):
    import nfl_lab.role_boosting as engine
    query, frozen, category = frozen_fixture()
    category = dict(category, target="pass_yd", support="signed_integer")
    frozen["target"] = "pass_yd"
    source = tmp_path / "old-frozen.parquet"
    frozen.to_parquet(source, index=False)
    output = tmp_path / "run"
    registry = {"output_directory": str(output), "categories": {"pass_yd": category},
        "old_base_forecasts": {"pass_yd": {"2022": {"path": str(source), "sha256": campaign.digest(source)}}}}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    monkeypatch.setattr(campaign, "load_prediction_inputs", lambda *_: (query, query, None, {"fictional": True}))
    def forbidden(*args, **kwargs):
        raise AssertionError("alias invoked model")
    monkeypatch.setattr(engine.RoleCountBoostingModel, "fit", forbidden)
    monkeypatch.setattr(engine, "prediction_rows", forbidden)
    for variant in ["A", "B"]:
        directory = output / "trials" / "pass_yd" / variant / "2022"
        directory.mkdir(parents=True)
        campaign.write_json(directory / "package-consumed.json", {})
        campaign.prediction_trial("fictional", directory, "pass_yd", variant, "2022")
        assert (directory / "candidate-frozen.parquet").read_bytes() == source.read_bytes()
        assert json.loads((directory / "prediction-manifest.json").read_text())["fit_attempts"] == 0
        with pytest.raises(FileExistsError, match="retries"):
            campaign.prediction_trial("fictional", directory, "pass_yd", variant, "2022")


def test_reports_primary_roles_all_offers_mse_and_week6_no_intervals():
    query, frozen, category = frozen_fixture()
    frozen.loc[frozen.index[0], "primary_role"] = False
    scored = score_frozen_rows(query, frozen, category)
    control = scored.copy()
    control["method"], control["point"] = "old_hgb", 5.
    report, _ = campaign.report_cell(scored, control, category, historical=True, pooled=True)
    primary = next(v for v in report["paired"] if v["status"] == "primary")
    assert primary["population"] == "prior_primary_roles" and primary["paired_rows"] == len(query) - 1
    assert len(report["paired"]) == 2
    assert report["summary"]["point_metrics"]["mse"] == pytest.approx(report["summary"]["point_metrics"]["rmse"] ** 2)
    assert {s["dimension"] for s in report["subgroups"]} >= {"position", "team", "opponent", "fallback"}
    control["method"] = "website"
    report, _ = campaign.report_cell(scored, control, category, historical=False)
    primary = next(v for v in report["paired"] if v["status"] == "primary")
    assert primary["population"] == "all_original_offered" and "intervals" not in primary
    assert len(report["common_all_controls"]) == 2


def test_binary_log_infinity_and_fixed_reliability_are_retained():
    query, frozen, category = frozen_fixture()
    category = dict(category, support="bernoulli")
    query["pass_att"] = 1.
    frozen["point"] = 0.
    scored = score_frozen_rows(query, frozen, category)
    control = scored.copy()
    control["method"], control["point"] = "website", 1.
    report, _ = campaign.report_cell(scored, control, category, historical=False)
    assert report["summary"]["log_loss_state"] == "positive_infinity"
    assert len(report["summary"]["reliability_deciles"]) == 10


def test_coherence_keeps_missing_offers_and_only_audits_common_points(tmp_path):
    query, frozen, _ = frozen_fixture()
    frames = {}
    for target, point in [("pass_cmp", 4.), ("pass_att", 3.), ("rush_rec_yd", 10.), ("rush_yd", 7.), ("rec_yd", 2.)]:
        frame = frozen.copy()
        frame["point"] = point
        frames[target, "A", "website_week6"] = frame.iloc[:-1] if target == "rec_yd" else frame
    reports = campaign.coherence_audits(frames, tmp_path / "coherence")
    completion = next(v for v in reports if v["variant"] == "A" and v["period"] == "website_week6" and v["audit"] == "completion_minus_attempt")
    combined = next(v for v in reports if v["variant"] == "A" and v["period"] == "website_week6" and v["audit"] == "direct_combined_minus_components")
    assert completion["positive_gap_rows"] == len(query)
    assert combined["common_available_rows"] == len(query) - 1 and combined["missing_component_rows"] == 1
    assert combined["mean_point_gap"] == 1.


def test_full_matrix_and_failure_consumption_precede_global_scoring(tmp_path, monkeypatch):
    _, _, base = fictional()
    passing = {"pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int"}
    categories = {t: dict(base, target=t, support="count" if t in {"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec"} else "bernoulli" if t == "anytime_td" else "signed_integer",
        modeled_roles=["QB"] if t in passing else ["RB", "WR", "TE"] if t == "anytime_td" else ["QB", "RB", "FB", "WR", "TE"],
        state="BLOCKED_LABEL_CONTRACT" if t == "fantasy_ppr" else "READY") for t in campaign.TARGETS}
    output = tmp_path / "run"
    registry = {"output_directory": str(output), "categories": categories}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    def fake_process(arguments, root, directory, **kwargs):
        if arguments[0] == "score-report":
            freeze = json.loads((output / "forecast-freeze.json").read_text())
            statuses = json.loads((output / "attempts.json").read_text())
            assert len(statuses) == 96 and freeze["fit_attempts"] == 136
            assert sum(s["state"] == "BLOCKED_CATEGORY_CONTRACT" for s in statuses) == 8
            assert sum(s.get("blocked_subfit_slots", 0) for s in statuses) == 24
            campaign.write_json(output / "score-consumed.json", {"score_passes": 1})
            campaign.write_json(output / "role-boosting-report.json", {})
        else:
            _, _, _, target, variant, period = arguments
            kind = package_kind(categories[target], variant)
            attempts = (1 if variant == "A" else len(categories[target]["modeled_roles"])) if kind == "model" else 0
            for i in range(attempts):
                campaign.write_json(directory / f"estimator-attempt-{i+1:02d}.json", {})
            if target == "rec" and variant == "B" and period == "2022":
                return {"returncode": 1, "cpu_seconds": 0.01, "reason": "FICTIONAL_CONSUMED_FAILURE"}
            campaign.write_json(directory / "prediction-manifest.json", {"bindings": {}, "fit_attempts": attempts})
        return {"returncode": 0, "cpu_seconds": 0.01, "reason": None}
    monkeypatch.setattr(campaign, "monitored_process", fake_process)
    path = tmp_path / "registry.json"
    campaign.write_json(path, registry)
    assert campaign.run(path, output)
    completion = json.loads((output / "completion.json").read_text())
    assert completion["fit_attempts_consumed"] == 136
    assert sum(s["state"] == "FAILED_CONSUMED" for s in completion["statuses"]) == 1
    with pytest.raises(FileExistsError, match="restart"):
        campaign.run(path, output)


def test_unsealed_and_payload_drift_rejected_before_any_inputs(tmp_path):
    path = tmp_path / "registry.json"
    campaign.write_json(path, {})
    with pytest.raises(ValueError, match="seal"):
        campaign.check_seal(path)
    plan = tmp_path / "plan.json"
    campaign.write_json(plan, {"fictional": True})
    campaign.write_json(path, {"state": "SEALED_ROOT_AND_REVIEWER", "fictional": False,
        "seal": {"integrator": "/root", "reviewer": "/root/fictional", "decision": "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY",
                 "reviewed_plan_path": str(plan), "reviewed_plan_sha256": campaign.digest(plan)}})
    with pytest.raises(ValueError, match="payload differs"):
        campaign.check_seal(path)


def test_exact_parent_source_and_old_forecast_freeze_are_required_by_seal(tmp_path):
    _, _, category = fictional()
    categories = {t: dict(category, target=t, state="BLOCKED_LABEL_CONTRACT" if t == "fantasy_ppr" else "READY") for t in campaign.TARGETS}
    dummy = tmp_path / "fictional-input.txt"
    dummy.write_text("fictional bytes; no NFL data\n")
    def binding(path):
        return {"path": str(path), "sha256": campaign.digest(path)}
    inputs = {k: binding(dummy) for k in ["training_features", "query_features", "opportunities", "outcomes"]}
    code = [binding(Path(campaign.__file__).with_name(n)) for n in [
        "role_boosting.py", "role_boosting_campaign.py", "median_boosting.py", "median_boosting_campaign.py",
        "median_boosting_evaluation.py", "cdf_engine.py", "cdf_campaign.py", "cdf_evaluation.py", "website_cdf.py", "website_cdf_evaluation.py"]]
    parent_output = tmp_path / "parent-run"
    old, frozen = {}, {}
    for target in campaign.TARGETS:
        if target == "fantasy_ppr":
            continue
        old[target] = {}
        for period in campaign.PERIODS:
            relative = f"trials/{target}/base/{period}/candidate-frozen.parquet"
            path = parent_output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fictional authenticated frozen bytes")
            old[target][period] = binding(path)
            frozen[relative] = campaign.digest(path)
    freeze = parent_output / "forecast-freeze.json"
    campaign.write_json(freeze, {"bindings": frozen})
    parent = tmp_path / "parent.json"
    campaign.write_json(parent, {"categories": categories, "inputs": inputs, "output_directory": str(parent_output), "source_packet_mode": "joint_learner_source_reconstruction"})
    prior, website, contract = [tmp_path / n for n in ["prior.json", "website.json", "contract.json"]]
    campaign.write_json(prior, {"categories": categories, "code_bindings": code})
    campaign.write_json(website, {"categories": categories})
    campaign.write_json(contract, {"state": "APPROVED_FREE_TRAINING_AND_INFERENCE", "inputs": inputs})
    controls = {t: {"base": {p: {m: binding(dummy) for m in (["old_cdf"] if p == "website_week6" else ["old_cdf", "pooled", "recent"])} for p in campaign.PERIODS}} for t in old}
    payload = {"registration_id": VERSION, "categories": categories, "model_design": DESIGN,
        "comparisons": campaign.COMPARISONS, "budgets": campaign.LIMITS, "variants": ["A", "B"],
        "periods": list(campaign.PERIODS), "output_directory": str(tmp_path / "output"), "inputs": inputs,
        "code_bindings": code, "prerequisite_bindings": [binding(freeze)], "old_base_forecasts": old,
        "saved_controls": controls, "parent_boosting_registry": binding(parent), "prior_registry": binding(prior),
        "website_registry": binding(website), "source_contract": binding(contract),
        "source_packet_mode": "joint_learner_source_reconstruction", "study_source_relation": "same_exact_parent_hgb_input_packet",
        "ensemble_design": {"enabled": False, "additional_fits": 0}}
    plan, sealed_path = tmp_path / "reviewed.json", tmp_path / "sealed.json"
    def seal():
        campaign.write_json(plan, dict(payload, state="FICTIONAL_REVIEW_READY"))
        campaign.write_json(sealed_path, dict(payload, state="SEALED_ROOT_AND_REVIEWER", seal={"integrator": "/root", "reviewer": "/root/fictional_reviewer",
            "decision": "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY", "reviewed_plan_path": str(plan), "reviewed_plan_sha256": campaign.digest(plan)}))
    seal()
    assert campaign.check_seal(sealed_path)["registration_id"] == VERSION
    original = payload["study_source_relation"]
    payload["study_source_relation"] = "different_packet"
    seal()
    with pytest.raises(ValueError, match="same-source"):
        campaign.check_seal(sealed_path)
    payload["study_source_relation"] = original
    payload["old_base_forecasts"]["pass_att"]["2022"] = binding(dummy)
    seal()
    with pytest.raises(ValueError, match="parent freeze"):
        campaign.check_seal(sealed_path)


def test_single_score_consumption_precedes_every_evaluation_read(tmp_path, monkeypatch):
    query, frozen, category = frozen_fixture()
    output = tmp_path / "run"
    output.mkdir()
    query = query.drop(columns=["pass_att"])
    opportunities = frozen[KEYS + ["target"]].copy()
    outcomes = opportunities.copy()
    outcomes["actual"], outcomes["participation_state"], outcomes["outcome_state"] = 4., "played", "played_nonzero"
    history = query.copy()
    paths = {}
    for key, frame in [("training_features", history), ("outcomes", outcomes), ("opportunities", opportunities), ("query_features", query)]:
        path = tmp_path / (key + ".parquet")
        frame.to_parquet(path, index=False)
        paths[key] = {"path": str(path), "sha256": campaign.digest(path)}
    categories = {t: dict(category, target=t, state="BLOCKED_LABEL_CONTRACT" if t == "fantasy_ppr" else "READY") for t in campaign.TARGETS}
    registry = dict(output_directory=str(output), categories=categories, inputs=paths,
        source_packet_mode="same_retained_packet", study_source_relation="same_exact_parent_hgb_input_packet",
        source_qualification="fictional", prior_search_and_exposure="fictional", saved_controls={"pass_att": {"base": {"website_week6": {}}}})
    statuses, bindings = [], {}
    for target in campaign.TARGETS:
        for variant in ["A", "B"]:
            for period in campaign.PERIODS:
                status = dict(target=target, variant=variant, period=period, fit_attempts=0)
                if target == "fantasy_ppr":
                    status.update(state="BLOCKED_CATEGORY_CONTRACT", blocked_subfit_slots=1 if variant == "A" else 5)
                elif target == "pass_att" and period == "website_week6":
                    relative = f"trials/{target}/{variant}/{period}"
                    status.update(state="PREDICTION_FROZEN", trial=relative)
                    directory = output / relative
                    directory.mkdir(parents=True)
                    query.to_parquet(directory / "query.parquet", index=False)
                    frozen.to_parquet(directory / "candidate-frozen.parquet", index=False)
                    frozen.to_parquet(directory / "old-hgb-frozen.parquet", index=False)
                    offers = opportunities.copy()
                    for field in ["website_point", "raw_point", "simple_point"]:
                        offers[field] = 4.
                    offers.to_parquet(directory / "literal-offers.parquet", index=False)
                    for path in directory.iterdir():
                        bindings[str(path.relative_to(output))] = campaign.digest(path)
                else:
                    status["state"] = "SKIPPED_FICTIONAL_BUDGET"
                statuses.append(status)
    campaign.write_json(output / "attempts.json", statuses)
    campaign.write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": campaign.digest(output / "attempts.json"), "fit_attempts": 0})
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    original_read = pd.read_parquet
    observed_reads = []
    def guarded_read(path, *args, **kwargs):
        assert (output / "score-consumed.json").is_file()
        observed_reads.append(str(path))
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", guarded_read)
    campaign.score_report("fictional-sealed.json", output)
    assert paths["outcomes"]["path"] in observed_reads
    report = json.loads((output / "role-boosting-report.json").read_text())
    assert len(report["slots"]) == 96 and len(report["primary_slots"]) == 48
    assert report["comparator_availability"]["2022"]["website"] == "N/A_not_recorded_for_exact_panel"
    before = len(observed_reads)
    with pytest.raises(FileExistsError):
        campaign.score_report("fictional-sealed.json", output)
    assert len(observed_reads) == before
