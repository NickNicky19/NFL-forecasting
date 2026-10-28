"""Unique football queries and unchanged-law fanout to market offer thresholds.

V1/V2 and their failures stay unchanged. Calibration, scoring, source filters,
probability formulas and selection are imported from the original fixed core.
"""
from __future__ import annotations

import hashlib
import json

from . import historical_market_comparison as core

VERSION = "historical-market-comparison-no2025-technical-v3-20261028"
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]


def reuse_context_abstentions(offers, abstentions):
    import pandas as pd
    unit = core.BOOK_UNIT
    core.require(not offers.duplicated(unit).any() and not abstentions.duplicated(unit).any(), "cached offer/mask keys duplicated")
    original = pd.MultiIndex.from_frame(offers[unit])
    rejected = pd.MultiIndex.from_frame(abstentions[unit])
    core.require(rejected.isin(original).all(), "cached abstention is not part of original offered pool")
    compatible = offers.loc[~original.isin(rejected)].copy().reset_index(drop=True)
    core.require(len(compatible) + len(abstentions) == len(offers), "cached context membership lost")
    return compatible


def unique_input(selected, query):
    """Return exact unique original features plus offer-to-query integer index."""
    import numpy as np
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    unique_keys = selected[core.KEYS].drop_duplicates().reset_index(drop=True)
    features = unique_keys.merge(query, on=core.KEYS, how="left", validate="one_to_one", sort=False)
    core.require(len(features) == len(unique_keys) and features.kickoff_utc.notna().all(), "unique original query missing")
    assert_clock_contract(features)  # The actual original guard, with no bypass.
    mapping = selected[core.KEYS].merge(unique_keys.assign(query_row=np.arange(len(unique_keys))),
        on=core.KEYS, how="left", validate="many_to_one", sort=False).query_row.to_numpy(int)
    expanded_context = features.iloc[mapping].reset_index(drop=True)
    for name in ["team", "opponent", "position"]:
        core.require(selected[name].astype(str).reset_index(drop=True).equals(expanded_context[name].astype(str)), "surviving context differs")
    core.require(pd.to_datetime(selected.kickoff_utc, utc=True).reset_index(drop=True).equals(
        pd.to_datetime(expanded_context.kickoff_utc, utc=True)), "surviving kickoff differs")
    core.require(len(mapping) == len(selected) and np.bincount(mapping).sum() == len(selected), "threshold fanout membership differs")
    return features, mapping


def frozen_point_context(plan, year, target, features):
    import pandas as pd
    ref = plan["models"][str(year)][target]
    frozen = json.loads(core.authenticate(ref["FROZEN.json"]).read_bytes())
    core.require(frozen["year"] == year and frozen["target"] == target and frozen["method"] == "leaf_cdf"
        and frozen["state"] == "PREDICTION_FROZEN", "original frozen point procedure metadata differs")
    saved = pd.read_parquet(core.authenticate(ref["forecast-frozen.parquet"]), columns=core.KEYS + CONTEXT + ["target", "method"])
    core.require(saved.target.eq(target).all() and saved.method.eq("leaf_cdf").all(), "frozen point identity differs")
    joined = features[core.KEYS + CONTEXT].merge(saved, on=core.KEYS, how="left", validate="one_to_one", sort=False,
        suffixes=("_query", "_frozen"))
    for name in CONTEXT:
        left, right = joined[name + "_query"], joined[name + "_frozen"]
        if name.endswith("_utc"):
            left, right = pd.to_datetime(left, utc=True), pd.to_datetime(right, utc=True)
        core.require(left.equals(right), "original frozen point/query context differs at preflight")


def preflight_queries(plan, offers, budget):
    """Check every real unique query frame before any model load/inference.

    Only original features and metadata are read here. The 2026 feature builder
    retains its permitted earlier outcome history behind individual cutoffs;
    no evaluation LOSS table or calibration labels are opened by this stage.
    """
    import gc
    import numpy as np
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    queries, records, feature_audits = {}, [], []
    for year in [2026, 2024, 2023, 2022]:
        if not offers.season.eq(year).any():
            continue
        if year == 2026:
            query, audit = core.build_2026_queries(plan, budget)
            feature_audits.append(audit)
        else:
            query = pd.read_parquet(core.authenticate(plan["historical_queries"][str(year)]))
            core.require(query.season.eq(year).all() and not set(plan["category_dependencies"]) & set(query), "original query contains wrong season/labels")
            query["participation_state"] = "unknown"
        assert_clock_contract(query)
        queries[year] = query
        for target in plan["category_dependencies"]:
            if target == "fantasy_ppr":
                continue
            selected = offers.loc[offers.season.eq(year) & offers.target.eq(target)].reset_index(drop=True)
            if selected.empty:
                continue
            features, mapping = unique_input(selected, query)
            if year != 2026:
                frozen_point_context(plan, year, target, features)
            fingerprint = hashlib.sha256(pd.util.hash_pandas_object(features, index=True).to_numpy().astype("<u8", copy=False).tobytes()).hexdigest()
            records.append({"year": year, "target": target, "unique_football_queries": len(features), "offered_threshold_rows": len(selected),
                "max_book_threshold_fanout": int(np.bincount(mapping).max()), "actual_original_clock_guard": "PASS",
                "original_feature_frame_sha256": fingerprint, "model_year": plan["model_for_season"][str(year)],
                "model_loads_predictions_labels_or_losses_in_preflight": 0})
            del features, mapping
            budget.check()
        gc.collect()
    core.require(records, "no real query frames available")
    return queries, records, feature_audits


def forecast_unique(plan, offers, budget, queries, preflight):
    """Apply one model per target/year and fan its rows to all actual offers."""
    import gc
    import joblib
    import numpy as np
    import pandas as pd
    from .cdf_engine import MixtureBatch
    forecasts, audits = [], []
    for year in [2026, 2024, 2023, 2022]:
        if year not in queries:
            continue
        model_year = plan["model_for_season"][str(year)]
        for target, category in plan["category_dependencies"].items():
            if target == "fantasy_ppr":
                continue
            selected = offers.loc[offers.season.eq(year) & offers.target.eq(target)].copy().reset_index(drop=True)
            if selected.empty:
                continue
            selected["primary_role"] = selected.position.isin(category["primary_roles"])
            selected["modeled_role"] = selected.position.isin(category["modeled_roles"])
            features, mapping = unique_input(selected, queries[year])
            fingerprint = hashlib.sha256(pd.util.hash_pandas_object(features, index=True).to_numpy().astype("<u8", copy=False).tobytes()).hexdigest()
            admitted = next(r for r in preflight if r["year"] == year and r["target"] == target)
            core.require(fingerprint == admitted["original_feature_frame_sha256"], "actual unique model input changed after preflight")
            ref = plan["models"][str(model_year)][target]
            budget.check("model_loads", 1)
            model = joblib.load(core.authenticate(ref["model.joblib"]))
            core.validate_model(model, target, model_year)
            budget.check("unique_football_queries", len(features))
            budget.check("law_query_rows", len(selected))
            budget.check("row_tree_evaluations", len(features) * 32)
            order = np.argsort(mapping, kind="stable")
            counts = np.bincount(mapping, minlength=len(features))
            groups = np.split(order, np.cumsum(counts)[:-1])
            for name in ["F_probability", "F_over", "F_under", "F_push", "F_mean", "F_point"]:
                selected[name] = np.nan
            selected["F_fallback"] = "unvisited"
            assigned = np.zeros(len(selected), bool)
            # This is the first actual prediction call, not a validation probe.
            for query_positions, law, reasons in model.predict_batches(features, batch_size=256):
                budget.check("law_batches", 1)
                per_query = [groups[int(q)] for q in query_positions]
                at = np.concatenate(per_query)
                local = np.repeat(np.arange(len(query_positions)), [len(x) for x in per_query])
                core.require(not assigned[at].any(), "duplicate threshold assignment")
                assigned[at] = True
                selected.loc[at, "F_fallback"] = np.repeat(reasons, [len(x) for x in per_query])
                if law is None:
                    continue
                expanded = MixtureBatch(law.support, law.weights[local], law.prior, prior_weight=law.b)
                products = core.law_products(expanded, selected.loc[at, "line"].to_numpy(float), event=target == "anytime_td")
                for name, values in products.items():
                    selected.loc[at, name] = values
                if year == 2026:
                    point = products["F_mean"] if category["support"] in ["count", "bernoulli"] else law.quantile(.5)[local]
                    selected.loc[at, "F_point"] = point
            core.require(assigned.all(), "some offered thresholds received no law assignment")
            selected.loc[~selected.probability_qualified, "F_probability"] = np.nan
            if year != 2026:
                name = "mean" if category["support"] in ["count", "bernoulli"] else "median"
                saved = pd.read_parquet(core.authenticate(ref["forecast-frozen.parquet"]), columns=core.KEYS + [name])
                original = selected[core.KEYS].merge(saved, on=core.KEYS, how="left", validate="many_to_one", sort=False)
                selected["F_point"] = original[name].to_numpy(float)
            selected["F_model_year"] = model_year
            selected["F_control_age"] = "frozen2024CDF trained2019–2023" if year == 2026 else "original earlier-season annualCDF"
            selected["evidence_lane"] = "NEW_UNIQUE_RAW_RETAINED_MODEL_NO2025_RECONSTRUCTION" if year == 2026 else "FROZEN_POINT_PLUS_NEW_MATCHED_THRESHOLD_QUERY"
            forecasts.append(selected)
            audits.append({**admitted, "model": ref["model.joblib"], "law_threshold_rows_assigned": int(assigned.sum()),
                "input_unit": "one original football feature row/player-game-target", "output_unit": "all admitted actualbookthreshold offers",
                "weights_atoms_prior_changed_for_fanout": False, "clock_guard_bypassed": False})
            del model, features
            gc.collect()
            budget.check()
    core.require(forecasts, "no genuine football threshold forecasts produced")
    return pd.concat(forecasts, ignore_index=True), audits
