"""A finite, no-2025 market comparison on independently qualified local inputs.

Importing this module performs no I/O or NFL arithmetic. The executable requires
an exact root/reviewer seal. All row artifacts use the existing managed store.
F is an authenticated retained CDF, FC a football-only calibration, FS a separate
confidence shrink, M an offering-book-excluded market view, and H the same
calibration learner as FC with the independent market input added.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import resource
import time

VERSION = "historical-market-comparison-no2025-v1-20261028"
KEYS = ["season", "week", "game_id", "player_id"]
UNIT = KEYS + ["target"]
SNAPSHOT = UNIT + ["source_collection_naive"]
BOOK_UNIT = UNIT + ["book_id"]
ARMS = ["F", "FC", "FS", "M", "H"]
META = KEYS + ["team", "opponent", "position", "kickoff_utc", "is_home"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binding(path):
    path = Path(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def authenticate(ref):
    path = Path(ref["path"])
    require(path.is_absolute() and path.resolve() == path, "canonical immutable input path required")
    require(binding(path) == {k: ref[k] for k in ["path", "bytes", "sha256"]}, "immutable input binding changed")
    if "blob" in ref:
        blob = Path(ref["blob"])
        require(blob.resolve() == blob and blob.name == ref["sha256"] and blob.samefile(path), "actual CAS alias/blob identity differs")
    return path


def read_capsule_member(ref):
    import zipfile
    with zipfile.ZipFile(authenticate(ref["container"])) as archive:
        body = archive.read(ref["member"])
    require(len(body) == ref["bytes"] and hashlib.sha256(body).hexdigest() == ref["sha256"], "capsule inner member bytes changed")
    return body


def clean(value):
    """Retain undefined/infinite metric states instead of JSON NaN or clipping."""
    import numpy as np
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return {"numeric_state": "missing" if np.isnan(value) else "positive_infinity" if value > 0 else "negative_infinity"}
    return value


@dataclass
class Budget:
    caps: dict
    start: float = field(default_factory=time.monotonic)
    cpu_start: float = field(default_factory=time.process_time)
    counts: dict = field(default_factory=dict)

    def check(self, name=None, amount=0):
        if name is not None:
            self.counts[name] = self.counts.get(name, 0) + amount
            require(self.counts[name] <= self.caps["maximum_" + name], "finite " + name + " cap exhausted")
        require(time.monotonic() - self.start < self.caps["wall_seconds"], "finite wall cap exhausted")
        require(time.process_time() - self.cpu_start < self.caps["CPU_seconds"], "finite CPU cap exhausted")
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= self.caps["RSS_bytes"], "finite RSS cap exhausted")

    def receipt(self):
        return {**self.counts, "CPU_seconds": time.process_time() - self.cpu_start,
                "wall_seconds": time.monotonic() - self.start,
                "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "base_CDF_fits": 0, "HTTP_calls": 0, "automatic_retries": 0}


def decimal_odds(values):
    import numpy as np
    values = np.asarray(values, float)
    require(np.isfinite(values).all() and ((values <= -100) | (values >= 100)).all(), "invalid American odds")
    result = np.empty(len(values))
    positive = values > 0
    result[positive] = 1 + values[positive] / 100
    result[~positive] = 1 + 100 / -values[~positive]
    return result


def crossing_mask(frame, groups, probability):
    """Abstain a complete observed threshold group on any upward over-p step."""
    import pandas as pd
    valid = frame.loc[frame[probability].notna()]
    ordered = valid.sort_values(groups + ["line"], kind="stable")
    increases = ordered.groupby(groups, observed=True, sort=False, dropna=False)[probability].diff().gt(0)
    rejected = ordered.loc[increases, groups].drop_duplicates()
    bad = pd.MultiIndex.from_frame(frame[groups]).isin(pd.MultiIndex.from_frame(rejected))
    return pd.Series(bad, index=frame.index)


def pair_and_canonicalize(rows, allowed_books):
    """Outcome-blind same-book pairing and offering-book-excluded market view.

    An absent ATD No quote stays absent. No cross-player normalization or fair
    probability is made from its one-sided Yes price. Source version conflicts
    have already been quarantined by the single source adapter.
    """
    import numpy as np
    import pandas as pd
    require(not rows.season.eq(2025).any(), "excluded season reached market adapter")
    required = set(META + ["target", "period", "side", "line", "american_odds", "book_id", "book_kind",
        "source_collection_naive", "source_eligible_exploratory", "identity_status", "duplicate_status",
        "source_row_number", "source_sha256", "source_member", "rejection_reasons"])
    require(required <= set(rows), "qualified normalized source contract incomplete")
    eligible = (rows.source_eligible_exploratory.eq(True) & rows.rejection_reasons.eq("")
        & rows.identity_status.eq("source_gsis_exact_historical_roster_schedule")
        & rows.duplicate_status.isin(["unique", "exact_duplicate_representative"])
        & rows.book_kind.eq("named") & rows.book_id.isin(allowed_books) & rows.period.eq("event")
        & rows.source_collection_naive.notna())
    good = rows.loc[eligible].copy()
    require(not good.book_id.isin([15, 30]).any(), "OPEN/CONSENSUS cannot enter named-book comparison")
    good["source_collection_naive"] = good.source_collection_naive.astype(str)
    good["decimal"] = decimal_odds(good.american_odds)
    good["suspect_extreme_price"] = good.american_odds.abs().ge(10000)
    pair_key = SNAPSHOT + ["period", "book_id", "line"]
    ordinary = good.loc[good.target.ne("anytime_td")]
    require(not ordinary.duplicated(pair_key + ["side"]).any(), "source adapter left ambiguous side quote")
    over = ordinary.loc[ordinary.side.eq("over")].copy()
    under = ordinary.loc[ordinary.side.eq("under"), pair_key + ["decimal", "source_row_number", "american_odds"]]
    paired = over.rename(columns={"decimal": "d_over"}).merge(
        under.rename(columns={"decimal": "d_under", "source_row_number": "under_source_row_number", "american_odds": "under_american_odds"}),
        on=pair_key, how="inner", validate="one_to_one", sort=False)
    paired["offering_fair_over"] = (1 / paired.d_over) / (1 / paired.d_over + 1 / paired.d_under)
    paired["price_qualified"] = ~paired.suspect_extreme_price & paired.under_american_odds.abs().lt(10000)
    paired["market_threshold_crossing"] = crossing_mask(paired.loc[paired.price_qualified], SNAPSHOT + ["book_id"], "offering_fair_over").reindex(paired.index, fill_value=False)
    paired["probability_qualified"] = paired.price_qualified & ~paired.market_threshold_crossing
    paired["raw_proportional_over"] = paired.offering_fair_over
    paired.loc[~paired.probability_qualified, "offering_fair_over"] = np.nan
    paired["even_distance"] = (paired.offering_fair_over - .5).abs()
    paired["quote_pair_status"] = "same_book_same_threshold_same_clock_two_sided"
    one_side = ordinary.sort_values(pair_key + ["side", "source_row_number"], kind="stable").drop_duplicates(pair_key).copy()
    paired_keys = pd.MultiIndex.from_frame(paired[pair_key])
    one_side = one_side.loc[~pd.MultiIndex.from_frame(one_side[pair_key]).isin(paired_keys)].copy()
    one_side["d_over"] = np.where(one_side.side.eq("over"), one_side.decimal, np.nan)
    one_side["d_under"] = np.where(one_side.side.eq("under"), one_side.decimal, np.nan)
    one_side["offering_fair_over"] = np.nan
    one_side["price_qualified"] = ~one_side.suspect_extreme_price
    one_side["probability_qualified"] = one_side.price_qualified
    one_side["market_threshold_crossing"] = False
    one_side["quote_pair_status"] = "one_sided_point_and_football_only_no_market_fair_probability"
    atd = good.loc[good.target.eq("anytime_td") & good.side.eq("noside") & good.line.eq(0)].copy()
    atd = atd.rename(columns={"decimal": "d_over"})
    atd["d_under"] = np.nan
    atd["offering_fair_over"] = np.nan
    atd["price_qualified"] = ~atd.suspect_extreme_price
    atd["probability_qualified"] = atd.price_qualified
    atd["market_threshold_crossing"] = False
    atd["under_source_row_number"] = np.nan
    atd["quote_pair_status"] = "one_sided_ATD_Yes_no_fair_probability_inferred"
    quotes = pd.concat([paired, one_side, atd], ignore_index=True)
    quotes["even_distance"] = (quotes.offering_fair_over - .5).abs().fillna(0.)
    quotes["pair_priority"] = (quotes.quote_pair_status.ne("same_book_same_threshold_same_clock_two_sided").astype(int)
        + 2 * (~quotes.probability_qualified).astype(int))
    # First exact collector snapshot is an outcome-blind deterministic horizon;
    # its naive time supplies no authenticated pregame availability claim.
    canonical = quotes.sort_values(BOOK_UNIT + ["source_collection_naive", "pair_priority", "even_distance", "line", "source_row_number"],
        kind="stable").drop_duplicates(BOOK_UNIT).reset_index(drop=True)
    require(not canonical.duplicated(BOOK_UNIT).any(), "canonical book opportunities duplicated")
    canonical["M_probability"] = np.nan
    canonical["M_point"] = np.nan
    canonical["independent_probability_books"] = ""
    canonical["independent_point_books"] = ""
    independent_crossings = {}
    # Each offering book has a separate feature/calibration panel; the same B
    # is removed from every independent source in that panel, including train.
    for offering in allowed_books:
        independent = paired.loc[paired.book_id.ne(offering) & paired.probability_qualified].copy()
        if independent.empty:
            continue
        per_book = independent.sort_values(SNAPSHOT + ["book_id", "even_distance", "line", "source_row_number"],
            kind="stable").drop_duplicates(SNAPSHOT + ["book_id"])
        point = per_book.groupby(SNAPSHOT, observed=True, dropna=False).agg(
            M_point=("line", "median"), independent_point_books=("book_id", lambda s: ",".join(map(str, sorted(set(s)))))).reset_index()
        probability = independent.groupby(SNAPSHOT + ["line"], observed=True, dropna=False).agg(
            M_probability=("offering_fair_over", "median"),
            independent_probability_books=("book_id", lambda s: ",".join(map(str, sorted(set(s)))))).reset_index()
        crossing = crossing_mask(probability, SNAPSHOT, "M_probability")
        independent_crossings[str(offering)] = {"abstained_threshold_rows": int(crossing.sum()),
            "abstained_groups": len(probability.loc[crossing, SNAPSHOT].drop_duplicates())}
        probability.loc[crossing, "M_probability"] = np.nan
        at = canonical.index[canonical.book_id.eq(offering)]
        current = canonical.loc[at, SNAPSHOT + ["line"]].merge(point, on=SNAPSHOT, how="left", validate="many_to_one", sort=False)
        current = current.merge(probability, on=SNAPSHOT + ["line"], how="left", validate="many_to_one", sort=False)
        require(len(current) == len(at), "independent book join changed offer count")
        for name in ["M_point", "M_probability", "independent_probability_books", "independent_point_books"]:
            canonical.loc[at, name] = current[name].to_numpy()
        for name in ["independent_probability_books", "independent_point_books"]:
            require(all(str(offering) not in str(v).split(",") for v in canonical.loc[at, name].dropna()),
                "offering book leaked into independent market features")
    audit = {"normalized_rows": len(rows), "source_eligible_rows": int(eligible.sum()),
        "same_book_paired_quotes": len(paired), "one_sided_ATD_quotes": len(atd), "canonical_offers": len(canonical),
        "one_sided_ordinary_point_only_quotes": len(one_side),
        "suspect_abs_American_ge10000_source_rows": int(good.suspect_extreme_price.sum()),
        "suspect_two_sided_pairs": int((~paired.price_qualified).sum()),
        "own_book_crossing_threshold_rows_abstained": int(paired.market_threshold_crossing.sum()),
        "independent_market_crossing_groups": independent_crossings,
        "independent_same_threshold_offers": int(canonical.M_probability.notna().sum()),
        "independent_point_offers": int(canonical.M_point.notna().sum()),
        "timing_lane": "timing-unverified exploratory", "ATD_market_fair_probability": "UNAVAILABLE_NO_NO_SIDE"}
    return canonical, audit


def law_products(law, thresholds, *, event=False):
    """Direct empirical sums avoid invalid cumulative-CDF boundary roundoff.

    This is a new threshold product from the retained law, with unchanged atoms,
    weights and prior. It never clips a probability or invents a point law.
    """
    import numpy as np
    threshold = np.asarray(thresholds, float)
    support = law.support[None, :]
    weights = law.weights
    over = law.a * np.sum(weights * (support > np.floor(threshold)[:, None]), axis=1)
    over += law.b * (1 - law.prior.cdf(np.floor(threshold)))
    under = law.a * np.sum(weights * (support <= (np.ceil(threshold) - 1)[:, None]), axis=1)
    under += law.b * law.prior.cdf(np.ceil(threshold) - 1)
    integer = threshold == np.floor(threshold)
    push = np.zeros(len(threshold))
    push[integer] = (law.a * np.sum(weights[integer] * (support == threshold[integer, None]), axis=1)
        + law.b * np.exp(law.prior.logpmf(threshold[integer])))
    for values in [over, under, push]:
        require(np.isfinite(values).all() and ((values >= 0) & (values <= 1)).all(), "invalid raw law probability")
    require(np.allclose(over + under + push, 1., atol=2e-12, rtol=0), "law settlement masses do not sum to one")
    if event:
        require(law.prior.support == "bernoulli" and (threshold == 0).all(), "ATD Yes requires genuine binary event law")
        # Source noside/0 means Yes. No TD is a loss, never a push at0.
        under = push.copy()
        push = np.zeros(len(threshold))
    denominator = over + under
    decisive = np.divide(over, denominator, out=np.full(len(over), np.nan), where=denominator > 0)
    stable_mean = law.a * np.sum(weights * law.support, axis=1) + law.b * law.prior.mean
    return {"F_probability": decisive, "F_over": over, "F_under": under, "F_push": push,
        "F_mean": stable_mean}


def validate_model(model, target, model_year):
    require(model.category["target"] == target and model.panel == "base", "retained model category/panel mismatch")
    require(model.audit["tree_parameters"]["n_estimators"] == 32, "fixed 32-tree control required")
    for frame in [model.training_binding, model.prior_training_binding]:
        require(frame is not None and "season" in frame and (frame.season < model_year).all()
            and not frame.season.eq(2025).any(), "retained model contains forbidden/later training season")
        require(set(frame.season.astype(int)) == set(range(2019, model_year)), "exact retained model2019..earlier-year coverage differs")


def build_2026_queries(plan, budget):
    """Discard saved f_ fields; filter 2025 before Arrow materializes history.

    W1–W4 outcomes can be earlier feature sources for later 2026 games. Their
    use is controlled by each strict cutoff and is not calibration evidence.
    W5 outcomes are not decoded in this feature stage.
    """
    import pandas as pd
    import pyarrow.dataset as ds
    from .features import build_features, PLAYER_STATS, TEAM_STATS
    from .cdf_engine import assert_clock_contract
    path = authenticate(plan["raw_primitive_container"])
    dataset = ds.dataset(path, format="parquet")
    primitive = list(dict.fromkeys(META + ["participation_state", "outcome_available_utc", "cutoff_utc"]
        + [c for c in PLAYER_STATS if c != "fantasy_ppr"] + ["team_stat_" + c for c in TEAM_STATS]))
    primitive = [c for c in primitive if c in dataset.schema.names]
    require(not any(c.startswith("f_") for c in primitive), "saved features entered no2025 reconstruction")
    history_filter = ((ds.field("season") >= 2019) & (ds.field("season") <= 2024)) | (
        (ds.field("season") == 2026) & (ds.field("week") <= 4))
    history = dataset.to_table(columns=primitive, filter=history_filter).to_pandas()
    future = dataset.to_table(columns=META + ["cutoff_utc", "outcome_available_utc"],
        filter=(ds.field("season") == 2026) & (ds.field("week") == 5)).to_pandas()
    future["participation_state"] = "unknown"
    raw = pd.concat([history, future], ignore_index=True)
    budget.check("source_rows_materialized", len(raw))
    require(not raw.season.eq(2025).any(), "2025 decoded before rolling windows")
    rebuilt = build_features(raw)
    columns = [c for c in rebuilt if c in META + ["cutoff_utc", "outcome_available_utc", "feature_max_source_available_utc"] or c.startswith("f_")]
    query = rebuilt.loc[rebuilt.season.eq(2026) & rebuilt.week.isin(plan["evaluation_2026_weeks"]), columns].copy()
    query["participation_state"] = "unknown"
    query = query.reset_index(drop=True)
    assert_clock_contract(query)
    return query, {"source_predicate": str(history_filter), "materialized_history_rows": len(history),
        "label_blind_W5_context_rows": len(future), "query_rows": len(query), "2025_rows": 0,
        "previous_f_columns_used": 0, "availability": "original explicit kickoff+7day reconstruction assumption",
        "timing_lane": "timing-unverified exploratory; no original publication attestation"}


def forecast_football(plan, offers, budget):
    import gc
    import joblib
    import numpy as np
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    forecasts, audits = [], []
    new_query = None
    for year in [2022, 2023, 2024, 2026]:
        model_year = plan["model_for_season"][str(year)]
        if year == 2026:
            if new_query is None:
                new_query, audit = build_2026_queries(plan, budget)
                audits.append(audit)
            query = new_query
        else:
            query = pd.read_parquet(authenticate(plan["historical_queries"][str(year)]))
            require(not query.season.eq(2025).any() and query.season.eq(year).all(), "historical query season changed")
            require(not set(plan["category_dependencies"]) & set(query), "historical query contains target labels")
            query["participation_state"] = "unknown"
            assert_clock_contract(query)
        for target, category in plan["category_dependencies"].items():
            if target == "fantasy_ppr":
                continue
            selected = offers.loc[offers.season.eq(year) & offers.target.eq(target)].copy()
            if selected.empty:
                continue
            selected["primary_role"] = selected.position.isin(category["primary_roles"])
            selected["modeled_role"] = selected.position.isin(category["modeled_roles"])
            compatible = pd.MultiIndex.from_frame(selected[KEYS]).isin(pd.MultiIndex.from_frame(query[KEYS]))
            audits.append({"year": year, "target": target, "all_canonical_offers": len(selected),
                "primary_role_offers": int(selected.primary_role.sum()), "secondary_role_offers": int((~selected.primary_role).sum()),
                "missing_original_football_query_context_abstentions": int((~compatible).sum()),
                "missing_query_role_counts": selected.loc[~compatible, "position"].value_counts().to_dict(),
                "preservation": "complete canonical pool retained separately; unsupported/postseason contexts never guessed"})
            selected = selected.loc[compatible].reset_index(drop=True)
            if selected.empty:
                continue
            ref = plan["models"][str(model_year)][target]
            budget.check("model_loads", 1)
            model = joblib.load(authenticate(ref["model.joblib"]))
            validate_model(model, target, model_year)
            frozen_metadata = json.loads(authenticate(ref["FROZEN.json"]).read_bytes())
            require(frozen_metadata["year"] == model_year and frozen_metadata["target"] == target
                and frozen_metadata["method"] == "leaf_cdf" and frozen_metadata["state"] == "PREDICTION_FROZEN",
                "retained annual package metadata differs")
            features = selected[KEYS].merge(query, on=KEYS, how="left", validate="many_to_one", sort=False)
            require(len(features) == len(selected) and features.kickoff_utc.notna().all(), "offered query context missing")
            for name in ["team", "opponent", "position"]:
                require(selected[name].astype(str).reset_index(drop=True).equals(features[name].astype(str).reset_index(drop=True)),
                    "qualified market and football query context differ")
            require(pd.to_datetime(selected.kickoff_utc, utc=True).reset_index(drop=True).equals(
                pd.to_datetime(features.kickoff_utc, utc=True).reset_index(drop=True)), "market/query kickoff differs")
            assert_clock_contract(features)
            audits.append({"year": year, "target": target, "model_year": model_year, "model": ref["model.joblib"],
                "new_query_rows": len(features), "new_input_columns": list(features),
                "new_input_frame_sha256": hashlib.sha256(pd.util.hash_pandas_object(features, index=True).to_numpy().astype("<u8", copy=False).tobytes()).hexdigest(),
                "runtime_identity": "separately versioned raw fitted estimator research reconstruction; not original artifact replay or live readiness" if year == 2026 else
                    "new threshold products; exact original frozen point vector reused after source query/context checks"})
            budget.check("law_query_rows", len(features))
            budget.check("row_tree_evaluations", len(features) * 32)
            for name in ["F_probability", "F_over", "F_under", "F_push", "F_mean", "F_point"]:
                selected[name] = np.nan
            selected["F_fallback"] = "unvisited"
            for at, law, reasons in model.predict_batches(features, batch_size=256):
                budget.check("law_batches", 1)
                selected.loc[at, "F_fallback"] = reasons
                if law is None:
                    continue
                products = law_products(law, selected.loc[at, "line"].to_numpy(float), event=target == "anytime_td")
                for name, value in products.items():
                    selected.loc[at, name] = value
                if year == 2026:
                    point = products["F_mean"] if category["support"] in ["count", "bernoulli"] else law.quantile(.5)
                    selected.loc[at, "F_point"] = point
            selected.loc[~selected.probability_qualified, "F_probability"] = np.nan
            if year != 2026:
                # Reuse the exact old vector. New law-at-line queries above are
                # explicitly separate products, not reruns of old point studies.
                point_name = "mean" if category["support"] in ["count", "bernoulli"] else "median"
                context = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
                saved = pd.read_parquet(authenticate(ref["forecast-frozen.parquet"]), columns=KEYS + context + ["target", "method", point_name])
                require(saved.target.eq(target).all() and saved.method.eq("leaf_cdf").all(), "frozen point procedure identity differs")
                old = features[KEYS + context].merge(saved, on=KEYS, how="left", validate="many_to_one", sort=False, suffixes=("_query", "_frozen"))
                for name in context:
                    left, right = old[name + "_query"], old[name + "_frozen"]
                    if name.endswith("_utc"):
                        left, right = pd.to_datetime(left, utc=True), pd.to_datetime(right, utc=True)
                    require(left.equals(right), "old point vector and exact original query context differ")
                selected["F_point"] = old[point_name].to_numpy(float)
            selected["F_model_year"] = model_year
            selected["F_control_age"] = "frozen2024CDF trained2019–2023" if year == 2026 else "original earlier-season annualCDF"
            selected["evidence_lane"] = "NEW_RAW_RETAINED_MODEL_NO2025_INPUT_RECONSTRUCTION" if year == 2026 else "FROZEN_POINT_PLUS_NEW_MATCHED_THRESHOLD_QUERY"
            forecasts.append(selected)
            del model, features
            gc.collect()
            budget.check()
    require(forecasts, "no compatible matched football forecasts")
    return pd.concat(forecasts, ignore_index=True), audits


def load_labels(plan, years):
    """Independent supported football labels, never source W/L or results."""
    import numpy as np
    import pandas as pd
    import pyarrow.dataset as ds
    from .cdf_engine import valid_support, assert_composite_contract
    require(set(years) <= {2022, 2023, 2024, 2026} and 2025 not in years, "forbidden label partition")
    frames = []
    for year in [y for y in years if y != 2026]:
        for target, ref in plan["historical_label_inputs"][str(year)].items():
            contract = plan["category_dependencies"][target]
            frame = pd.read_parquet(authenticate(ref), columns=KEYS + ["participation_state", "outcome_state", "actual"])
            require(frame.season.eq(year).all() and not frame.duplicated(KEYS).any(), "retained label partition changed")
            frame = frame.rename(columns={"outcome_state": "original_outcome_state"})
            good = frame.participation_state.eq("played") & valid_support(frame.actual.to_numpy(float), contract["support"])
            frame["outcome_state"] = np.where(good, "supported_played", np.where(frame.participation_state.eq("DNP"), "known_DNP_void",
                np.where(frame.participation_state.eq("played"), "played_missing_or_invalid_statistic", "unknown_participation")))
            frame.loc[~good, "actual"] = np.nan
            frame["target"] = target
            frame["label_source"] = "exact_retained_same_source_scored_outcomes_not_recomputed"
            frames.append(frame)
    if 2026 not in years:
        return pd.concat(frames, ignore_index=True)
    dataset = ds.dataset(authenticate(plan["raw_primitive_container"]), format="parquet")
    targets = [t for t in plan["category_dependencies"] if t != "fantasy_ppr"]
    columns = list(dict.fromkeys(KEYS + ["position", "participation_state", "rush_td", "rec_td", "rush_yd", "rec_yd"] + targets))
    predicate = (ds.field("season") == 2026) & ds.field("week").isin(plan["evaluation_2026_weeks"])
    raw = dataset.to_table(columns=columns, filter=predicate).to_pandas()
    require(not raw.season.eq(2025).any() and not raw.duplicated(KEYS).any(), "forbidden/duplicate label rows")
    for target in targets:
        contract = plan["category_dependencies"][target]
        category = {"target": target}
        assert_composite_contract(raw, category)
        frame = raw[KEYS + ["participation_state", target]].rename(columns={target: "actual"}).copy()
        frame["target"] = target
        good = frame.participation_state.eq("played") & valid_support(frame.actual.to_numpy(float), contract["support"])
        frame["outcome_state"] = np.where(good, "supported_played", np.where(frame.participation_state.eq("DNP"), "known_DNP_void",
            np.where(frame.participation_state.eq("played"), "played_missing_or_invalid_statistic", "unknown_participation")))
        frame.loc[~good, "actual"] = np.nan
        frame["label_source"] = "independent_qualified_football_primitive_source_not_market_results"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def fit_ridge(train_x, train_y, alpha):
    import numpy as np
    from scipy.optimize import lsq_linear
    center = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale == 0] = 1
    x = np.column_stack([np.ones(len(train_x)), (train_x - center) / scale])
    penalty = np.diag([0.] + [alpha ** .5] * train_x.shape[1])
    augmented_x = np.vstack([x, penalty])
    augmented_y = np.r_[train_y, np.zeros(x.shape[1])]
    result = lsq_linear(augmented_x, augmented_y, bounds=([-np.inf] + [0.] * train_x.shape[1], [np.inf] * x.shape[1]),
        tol=1e-10, max_iter=200, lsq_solver="exact")
    require(result.success, "fixed nonnegative ridge optimizer failed")
    coef = result.x
    return {"center": center, "scale": scale, "coef": coef}


def apply_ridge(model, values):
    import numpy as np
    return np.column_stack([np.ones(len(values)), (values - model["center"]) / model["scale"]]) @ model["coef"]


def fit_logistic(train_x, train_y):
    """Same fixed convex learner for FC/H, with nonnegative input slopes."""
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit, logit
    def objective(beta):
        eta = beta[0] + train_x @ beta[1:]
        residual = expit(eta) - train_y
        value = np.sum(np.logaddexp(0., eta) - train_y * eta) + 5. * np.sum(beta[1:] ** 2)
        gradient = np.r_[np.sum(residual), train_x.T @ residual + 10. * beta[1:]]
        return value, gradient
    initial = np.r_[logit(np.mean(train_y)), np.zeros(train_x.shape[1])]
    result = minimize(objective, initial, jac=True, method="L-BFGS-B", bounds=[(None, None)] + [(0., None)] * train_x.shape[1],
        options={"maxiter": 200, "ftol": 1e-12, "gtol": 1e-8})
    require(result.success, "fixed nonnegative logistic optimizer failed")
    return {"coef": result.x[1:], "intercept": float(result.x[0]), "iterations": int(result.nit)}


def calibrate(plan, football, labels, budget):
    """Fit only on 2022/2023; apply fixed parameters to both outer years."""
    import numpy as np
    from scipy.special import expit, logit
    data = football.copy()
    data["FC_point"] = data.F_point
    data["H_point"] = np.nan
    for name in ["FC_probability", "FS_probability"]:
        data[name] = data.F_probability
    data["H_probability"] = np.nan
    train = data.loc[data.season.isin(plan["calibration_training_seasons"])].merge(
        labels, on=UNIT, how="left", validate="many_to_one", sort=False)
    require(not train.season.isin([2024, 2025, 2026]).any(), "outer outcomes reached calibration")
    records = []
    for target, contract in plan["category_dependencies"].items():
        if target == "fantasy_ppr":
            continue
        for book in plan["books"]["offering_book_ids"]:
            current = data.index[data.target.eq(target) & data.book_id.eq(book) & data.primary_role]
            earlier = train.loc[train.target.eq(target) & train.book_id.eq(book) & train.primary_role & train.outcome_state.eq("supported_played")].copy()
            record = {"target": target, "excluded_offering_book": book, "training_seasons": [2022, 2023],
                "point": "FALLBACK_F_AND_NO_H", "probability": "FALLBACK_F_AND_NO_H", "shrink": "FALLBACK_Q1"}
            if contract["support"] != "bernoulli":
                fitting = earlier.loc[np.isfinite(earlier.F_point) & np.isfinite(earlier.M_point)]
                if len(fitting) >= 100 and fitting[KEYS].drop_duplicates().shape[0] == len(fitting):
                    point_models = {}
                    for arm, columns in [("FC", ["F_point"]), ("H", ["F_point", "M_point"])]:
                        budget.check("meta_fits", 1)
                        model = fit_ridge(fitting[columns].to_numpy(float), fitting.actual.to_numpy(float), 10.)
                        point_models[arm] = model
                        good = current[np.isfinite(data.loc[current, columns]).all(axis=1)]
                        data.loc[good, arm + "_point"] = apply_ridge(model, data.loc[good, columns].to_numpy(float))
                        if contract["support"] == "count":
                            # A declared nonnegative point correction, no law or
                            # mean identity is claimed for this fitted point.
                            data.loc[good, arm + "_point"] = np.maximum(0., data.loc[good, arm + "_point"])
                    record["point"] = {"rows": len(fitting), "models": point_models}
            decisive = earlier.actual.ne(earlier.line) | earlier.target.eq("anytime_td")
            fitting = earlier.loc[decisive & earlier.F_probability.gt(0) & earlier.F_probability.lt(1)
                & earlier.M_probability.gt(0) & earlier.M_probability.lt(1)].copy()
            fitting["over_label"] = fitting.actual.gt(fitting.line).astype(int)
            classes = fitting.over_label.value_counts()
            if len(fitting) >= 100 and len(classes) == 2 and classes.min() >= 10:
                models = {}
                for arm, columns in [("FC", ["F_probability"]), ("H", ["F_probability", "M_probability"])]:
                    budget.check("meta_fits", 1)
                    model = fit_logistic(logit(fitting[columns].to_numpy(float)), fitting.over_label.to_numpy(int))
                    models[arm] = {"columns": columns, **model}
                    valid = data.loc[current, columns].gt(0).all(axis=1) & data.loc[current, columns].lt(1).all(axis=1)
                    at = current[valid]
                    data.loc[at, arm + "_probability"] = expit(logit(data.loc[at, columns].to_numpy(float)) @ model["coef"] + model["intercept"])
                record["probability"] = {"rows": len(fitting), "class_counts": classes.to_dict(), "models": models}
            shrink = earlier.loc[decisive & earlier.F_probability.between(0, 1)]
            if len(shrink) >= 100:
                budget.check("meta_fits", 1)
                x = shrink.F_probability.to_numpy(float) - .5
                y = shrink.actual.gt(shrink.line).to_numpy(float) - .5
                q = float(np.maximum(0., np.minimum(1., np.sum(x * y) / (np.sum(x * x) + 10.))))
                data.loc[current, "FS_probability"] = .5 + q * (data.loc[current, "F_probability"] - .5)
                record["shrink"] = {"q": q, "rows": len(shrink), "estimator": "constrained Brier slope; ridge10 toward q0; q in[0,1]"}
            records.append(record)
            budget.check()
    monotonicity = {"record_type": "probability_monotonicity", "semantics": "line-specific conditional probabilities, not complete CDFs",
        "canonical_thresholds_per_group": "one; source fair probability is additionally checked across all original paired thresholds before canonical selection",
        "nonnegative_FC_and_H_input_slopes": True, "FS_shrink_q_bounds": [0, 1], "crossings": {}}
    for arm in ARMS:
        mask = crossing_mask(data, BOOK_UNIT + ["source_collection_naive"], arm + "_probability")
        monotonicity["crossings"][arm] = {"abstained_rows": int(mask.sum()), "abstained_groups": len(data.loc[mask, BOOK_UNIT].drop_duplicates())}
        data.loc[mask, arm + "_probability"] = np.nan
    records.append(monotonicity)
    return data, records


def primary_offers(frame):
    """One player/game/stat/horizon, with fixed 68,69,79 book priority."""
    return frame.sort_values(UNIT + ["book_id", "source_collection_naive", "line", "source_row_number"],
        kind="stable").drop_duplicates(UNIT).reset_index(drop=True)


def paper_lists(frame):
    """Freeze five fixed rankings before evaluation outcomes are opened."""
    import numpy as np
    import pandas as pd
    common = frame.loc[frame[[a + "_probability" for a in ARMS]].notna().all(axis=1)
        & frame.F_point.notna() & frame.d_under.notna()].copy()
    common = primary_offers(common)
    result = []
    policies = {"projectiongap": "F", "footballEV": "F", "independentmarketEV": "M", "hybridEV": "H", "probabilityfirst": "FC"}
    for policy, arm in policies.items():
        p = common[arm + "_probability"].to_numpy(float)
        over_ev, under_ev = p * common.d_over.to_numpy(float) - 1, (1 - p) * common.d_under.to_numpy(float) - 1
        over = common.F_point.gt(common.line).to_numpy() if policy == "projectiongap" else over_ev >= under_ev
        selected = common.copy()
        selected["policy"] = policy
        selected["side"] = np.where(over, "over", "under")
        selected["conditional_probability"] = np.where(over, p, 1 - p)
        selected["decimal_odds"] = np.where(over, common.d_over, common.d_under)
        selected["conditional_EV"] = np.where(over, over_ev, under_ev)
        selected["score"] = ((common.F_point - common.line).abs() if policy == "projectiongap" else
            selected.conditional_probability if policy == "probabilityfirst" else selected.conditional_EV)
        selected = selected.loc[selected.conditional_EV.gt(.02)]
        if policy == "projectiongap":
            selected = selected.loc[selected.F_point.ne(selected.line)]
        selected = selected.sort_values(["season", "week", "target", "score", "game_id", "player_id", "book_id", "line", "side"],
            ascending=[True, True, True, False, True, True, True, True, True], kind="stable")
        selected = selected.groupby(["season", "week", "target"], sort=False, observed=True).head(5)
        selected["settlement_contract"] = "EXPLORATORY_ASSUMED_REFUND_PUSH_VOID_ACTUAL_BOOK_UNQUALIFIED"
        result.append(selected)
    return pd.concat(result, ignore_index=True) if result else common.iloc[:0].copy()


def probability_metrics(p, y):
    import numpy as np
    p, y = np.asarray(p, float), np.asarray(y, float)
    require(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all() and np.isin(y, [0, 1]).all(), "invalid probability scoring inputs")
    with np.errstate(divide="ignore"):
        losses = np.where(y == 1, -np.log(p), -np.log1p(-p))
    bins = []
    for i in range(10):
        at = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        bins.append({"lower": i / 10, "upper": (i + 1) / 10, "rows": int(at.sum()),
            "mean_p": float(p[at].mean()) if at.any() else None, "event_rate": float(y[at].mean()) if at.any() else None})
    return {"rows": len(p), "Brier": float(np.mean((p - y) ** 2)), "log_loss": float(losses.mean()),
        "infinite_log_losses": int(np.isposinf(losses).sum()), "calibration_bins": bins}


def paired_interval(frame, differences, cluster, seed=1703, replicates=500):
    import numpy as np
    import pandas as pd
    data = pd.DataFrame({"cluster": frame[cluster].to_numpy(), "difference": differences})
    grouped = data.groupby("cluster", observed=True).difference.agg(["sum", "count"])
    if len(grouped) < 8:
        return {"state": "N_A_FEWER_THAN_8_CLUSTERS", "clusters": len(grouped)}
    rng = np.random.default_rng(seed)
    choice = rng.integers(0, len(grouped), size=(replicates, len(grouped)))
    values = grouped["sum"].to_numpy()[choice].sum(axis=1) / grouped["count"].to_numpy()[choice].sum(axis=1)
    return {"state": "EXPOSED_SAMPLE_NOMINAL_INTERVAL", "clusters": len(grouped), "replicates": replicates,
        "mean_loss_difference": float(np.mean(differences)), "lower95": float(np.quantile(values, .025)), "upper95": float(np.quantile(values, .975))}


def score(plan, forecasts, labels, paper, budget):
    import numpy as np
    matched = forecasts.merge(labels, on=UNIT, how="left", validate="many_to_one", sort=False)
    supported = matched.loc[matched.outcome_state.eq("supported_played")].copy()
    primary_supported = supported.loc[supported.primary_role].copy()
    reports = []
    for (year, target), raw in primary_supported.groupby(["season", "target"], sort=True, observed=True):
        budget.check()
        contract = plan["category_dependencies"][target]
        point_common = raw.loc[raw[[a + "_point" for a in ["F", "FC", "H"]] + ["M_point"]].notna().all(axis=1)]
        point = primary_offers(point_common)
        point_rows = []
        if contract["support"] != "bernoulli" and len(point):
            threshold = 10 if contract["support"] == "signed_integer" else 1
            for arm in ["F", "FC", "M", "H", "OFFERED_LINE_HEURISTIC"]:
                values = point.line if arm == "OFFERED_LINE_HEURISTIC" else point[arm + "_point"]
                error = values.to_numpy(float) - point.actual.to_numpy(float)
                absolute = np.abs(error)
                side_correct = np.sign(values - point.line) == np.sign(point.actual - point.line)
                decisive = point.actual.ne(point.line) & values.ne(point.line)
                metric = {"arm": arm, "rows": len(point), "MAE": float(absolute.mean()), "MSE": float(np.mean(error ** 2)),
                    "RMSE": float(np.sqrt(np.mean(error ** 2))), "bias": float(error.mean()), "close_threshold": threshold,
                    "strict_close_rate": float(np.mean(absolute < threshold)), "inclusive_close_rate": float(np.mean(absolute <= threshold)),
                    "side_correct_and_strict_close_rate": float(np.mean(side_correct & decisive & (absolute < threshold))),
                    "side_correct_and_inclusive_close_rate": float(np.mean(side_correct & decisive & (absolute <= threshold)))}
                metric["point_product_semantics"] = ("actual retained CDF mean" if contract["support"] == "count" else "actual retained full-CDF lower median") if arm == "F" else (
                    "nonnegative-slope L2 ridge empirical point correction; no CDF mean/median identity or release eligibility claimed" if arm in ["FC", "H"] else
                    "line-as-point heuristic; no mean/median/distribution identity")
                baseline = point.F_point.to_numpy(float) - point.actual.to_numpy(float)
                diff = (error ** 2 - baseline ** 2) if contract["support"] == "count" else (absolute - np.abs(baseline))
                metric["paired_vs_F_game"] = paired_interval(point, diff, "game_id")
                metric["paired_vs_F_week"] = paired_interval(point, diff, "week")
                point_rows.append(metric)
        probability = raw.loc[raw[[a + "_probability" for a in ARMS]].notna().all(axis=1) & raw.d_under.notna()]
        probability = primary_offers(probability)
        probability = probability.loc[probability.actual.ne(probability.line)]
        probability_rows = []
        if len(probability):
            y = probability.actual.gt(probability.line).to_numpy(int)
            for arm in ARMS:
                p = probability[arm + "_probability"].to_numpy(float)
                report = {"arm": arm, **probability_metrics(p, y), "probability_semantics": "conditional on played and decisive"}
                difference = (p - y) ** 2 - (probability.F_probability.to_numpy(float) - y) ** 2
                report["paired_vs_F_game"] = paired_interval(probability, difference, "game_id")
                report["paired_vs_F_week"] = paired_interval(probability, difference, "week")
                probability_rows.append(report)
        standalone = primary_offers(raw.loc[raw.F_probability.notna()])
        standalone = standalone.loc[standalone.actual.ne(standalone.line) | standalone.target.eq("anytime_td")]
        standalone_rows = []
        if len(standalone):
            y = standalone.actual.gt(standalone.line).to_numpy(int)
            for arm in ["F", "FC", "FS"]:
                standalone_rows.append({"arm": arm, **probability_metrics(standalone[arm + "_probability"], y)})
        football_point_rows = []
        if contract["support"] != "bernoulli":
            standalone_point = primary_offers(raw.loc[raw.F_point.notna()])
            for arm in ["F", "OFFERED_LINE_HEURISTIC"]:
                values = standalone_point.F_point if arm == "F" else standalone_point.line
                error = values.to_numpy(float) - standalone_point.actual.to_numpy(float)
                if len(error):
                    football_point_rows.append({"arm": arm, "rows": len(error), "MAE": float(np.abs(error).mean()),
                        "MSE": float(np.mean(error ** 2)), "RMSE": float(np.sqrt(np.mean(error ** 2))), "bias": float(error.mean())})
        # Only F supplies actual push mass. ATD Yes is an event; zero TD is
        # a loss and must never enter this ordinary O/U push diagnostic.
        push_pool = primary_offers(raw.loc[raw.target.ne("anytime_td") & raw.F_push.notna() & raw.probability_qualified])
        push_report = {"state": "N_A_NO_SUPPORTED_ORDINARY_ROWS", "rows": 0}
        if len(push_pool):
            push_report = {"state": "F_RAW_LAW_ONLY", **probability_metrics(push_pool.F_push.to_numpy(float),
                push_pool.actual.eq(push_pool.line).to_numpy(int)), "other_arms_push_law": "NOT_INFERRED"}
        reports.append({"season": int(year), "target": target, "population": "prespecified_primary_roles", "role": contract["primary_roles"],
            "offered": len(forecasts.loc[forecasts.season.eq(year) & forecasts.target.eq(target) & forecasts.primary_role]),
            "supported_before_book_dedupe": len(raw), "unique_supported_player_games": len(primary_offers(raw)),
            "all_offered_outcome_states": matched.loc[matched.season.eq(year) & matched.target.eq(target), "outcome_state"].value_counts(dropna=False).to_dict(),
            "point_common_pool": point_rows, "football_vs_offered_line_standalone": football_point_rows,
            "probability_common_pool": probability_rows, "football_probability_standalone": standalone_rows,
            "F_push_probability_separate": push_report})
    paper_grade = paper.merge(labels, on=UNIT, how="left", validate="many_to_one", sort=False)
    paper_grade["net_units"] = np.nan
    paper_grade["settlement"] = "unknown_ungraded"
    good = paper_grade.outcome_state.eq("supported_played")
    push = good & paper_grade.actual.eq(paper_grade.line)
    void = paper_grade.outcome_state.eq("known_DNP_void")
    wins = good & ~push & ((paper_grade.side.eq("over") & paper_grade.actual.gt(paper_grade.line)) | (paper_grade.side.eq("under") & paper_grade.actual.lt(paper_grade.line)))
    losses = good & ~push & ~wins
    paper_grade.loc[wins, "net_units"] = paper_grade.loc[wins, "decimal_odds"] - 1
    paper_grade.loc[losses, "net_units"] = -1
    paper_grade.loc[push | void, "net_units"] = 0
    for mask, name in [(wins, "assumed_win"), (losses, "assumed_loss"), (push, "assumed_push_refund"), (void, "assumed_DNP_void_refund")]:
        paper_grade.loc[mask, "settlement"] = name
    paper_summary = []
    for (year, target, policy), group in paper_grade.groupby(["season", "target", "policy"], observed=True):
        paper_summary.append({"season": int(year), "target": target, "policy": policy, "selected": len(group),
            "settlement_states": group.settlement.value_counts().to_dict(), "assumed_net_units_known_only": float(group.net_units.sum(min_count=1)),
            "weekly": [{"week": int(week), "selected": len(g), "graded": int(g.net_units.notna().sum()),
                "assumed_net_units_known_only": float(g.net_units.sum(min_count=1))} for week, g in group.groupby("week", observed=True)],
            "claim": "timing-unverified hypothetical assumed settlement; actual book settlement UNQUALIFIED; no profitability claim"})
    dependency_rows = []
    for year in [2024, 2026]:
        for target, contract in plan["category_dependencies"].items():
            offered = forecasts.loc[forecasts.season.eq(year) & forecasts.target.eq(target)]
            available = supported.loc[supported.season.eq(year) & supported.target.eq(target)]
            dependency_rows.append({"season": year, "target": target,
                "state": "BLOCKED_EXACT_PPR_LABEL_AND_NO_SOURCE_MARKET" if target == "fantasy_ppr" else
                    "NO_COMPATIBLE_MATCHED_SOURCE" if offered.empty else "NO_SUPPORTED_OUTCOMES" if available.empty else "SUPPORTED_EXPLORATORY",
                "canonical_book_offers": len(offered), "supported_unique_player_games": len(primary_offers(available)),
                "primary_role_forecast_offers": int(offered.primary_role.sum()) if len(offered) else 0,
                "secondary_role_forecast_offers": int((~offered.primary_role).sum()) if len(offered) else 0,
                "fallback_counts_all_roles": offered.F_fallback.value_counts(dropna=False).to_dict() if len(offered) else {},
                "market_probability_offers": int(offered.M_probability.notna().sum()) if len(offered) else 0,
                "primary_roles": contract["primary_roles"]})
    secondary = []
    for (year, target), raw in supported.groupby(["season", "target"], observed=True):
        population = primary_offers(raw)
        numeric = plan["category_dependencies"][target]["support"] != "bernoulli"
        points = []
        if numeric:
            for arm in ["F", "M", "OFFERED_LINE_HEURISTIC"]:
                values = population.line if arm == "OFFERED_LINE_HEURISTIC" else population[arm + "_point"]
                valid = values.notna()
                error = values.loc[valid].to_numpy(float) - population.loc[valid, "actual"].to_numpy(float)
                points.append({"arm": arm, "rows": len(error), "MAE": float(np.mean(np.abs(error))) if len(error) else None,
                    "MSE": float(np.mean(error ** 2)) if len(error) else None})
        decisive = population.loc[population.F_probability.notna() & (population.actual.ne(population.line) | population.target.eq("anytime_td"))]
        secondary.append({"season": int(year), "target": target, "population": "secondary_all_compatible_offered_roles_not_primary_role_claim",
            "rows": len(population), "role_counts": population.position.value_counts().to_dict(),
            "CDF_fallback_counts": population.F_fallback.value_counts(dropna=False).to_dict(), "point_coverage_metrics": points,
            "F_probability": probability_metrics(decisive.F_probability, decisive.actual.gt(decisive.line).astype(int)) if len(decisive) else None,
            "FC_FS_H_scope": "earlier calibration and paper selection restricted to prespecified primary roles; no extrapolated correction claim"})
    return {"categories": reports, "all_role_secondary": secondary, "all12_dependency_rows": dependency_rows, "paper": paper_summary, "PPR": "BLOCKED_EXACT_LABEL_AND_NO_SOURCE_MARKET",
        "GAP_SCREENED_identity": "laboratory F point-gap proxy screened by genuine F probability/price; not recorded historical website Top Over/Under; compatible historical SITE/R0 absent",
        "control_limitation": "2026 F is a frozen2024 law trained2019–2023; age may worsen its result; no strong contemporaneous control is claimed",
        "timing_lane": "timing-unverified exploratory; current-vintage reconstructed football features",
        "development": "2022/2023 calibration development only; repeatedly exposed history; 2024 and2026 are not independent scientific confirmation"}, matched, paper_grade
