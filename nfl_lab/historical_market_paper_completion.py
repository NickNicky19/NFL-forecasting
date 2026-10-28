"""Zero-fit accounting of immutable hypothetical paper lists and offered rows.

No transport, model load, probability transformation, ranking or selection runs
here. Unknown selected settlements stay unknown; policy abstentions are explicit
zero-action packets on the frozen common opportunity population.
"""
from __future__ import annotations

import csv
import itertools
import math

import numpy as np
import pandas as pd

VERSION = "historical-market-paper-completion-v1"
UNIT = ["season", "week", "game_id", "player_id", "target"]
OFFER = UNIT + ["book_id", "line", "source_collection_naive"]
POLICIES = ("projectiongap", "footballEV", "independentmarketEV", "hybridEV", "probabilityfirst")
ARMS = ("F", "FC", "M", "H")
PROBABILITIES = [arm + "_probability" for arm in ("F", "FC", "FS", "M", "H")]
STATES = ("assumed_win", "assumed_loss", "assumed_push_refund", "assumed_DNP_void_refund", "unknown_ungraded")
DISPLAY_COLUMNS = UNIT + ["kickoff_utc", "team", "opponent", "position", "primary_role", "book_id", "line", "side",
    "american_odds", "under_american_odds", "d_over", "d_under", "source_collection_naive", "source_sha256",
    "source_member", "source_row_number", "under_source_row_number", "quote_pair_status", "price_qualified", "probability_qualified",
    "independent_probability_books", "independent_point_books", "F_model_year", "F_control_age", "F_fallback", "evidence_lane",
    "F_point", "FC_point", "M_point", "H_point", "F_mean", "F_over", "F_under", "F_push"] + PROBABILITIES
MATCHED_COLUMNS = DISPLAY_COLUMNS + ["actual", "participation_state", "outcome_state", "label_source"]
FORECAST_COLUMNS = OFFER + ["kickoff_utc", "source_row_number", "F_point", "FC_point", "M_point", "H_point", "d_over", "d_under"] + PROBABILITIES
PAPER_COLUMNS = OFFER + ["policy", "side", "decimal_odds", "conditional_probability", "conditional_EV", "score"]
GRADE_COLUMNS = PAPER_COLUMNS + ["actual", "participation_state", "outcome_state", "net_units", "settlement"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _ratio(a, b):
    return float(a / b) if b else None


def _index(frame, columns=OFFER):
    return pd.MultiIndex.from_frame(frame[columns])


def _equal(left, right):
    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        return np.array_equal(left.to_numpy(float), right.to_numpy(float), equal_nan=True)
    a, b = left.astype(object), right.astype(object)
    return bool((a.eq(b) | (a.isna() & b.isna())).all())


def validate_packets(forecasts, matched, frozen, graded):
    """Authenticate relationships without recomputing any forecast or grade."""
    for frame in [forecasts, matched, frozen, graded]:
        require(set(frame.season.unique()) <= {2024, 2026}, "excluded season in frozen evaluation packet")
    fi, mi = _index(forecasts), _index(matched)
    require(fi.is_unique and mi.is_unique and len(fi) == len(mi), "offered row membership duplicated or changed")
    order = fi.get_indexer(mi)
    require((order >= 0).all(), "graded offer absent from frozen forecasts")
    aligned = forecasts.iloc[order].reset_index(drop=True)
    for column in set(forecasts) & set(matched):
        require(_equal(aligned[column], matched[column].reset_index(drop=True)), "frozen forecast field changed: " + column)
    keys = ["policy"] + OFFER
    a, b = _index(frozen, keys), _index(graded, keys)
    require(a.is_unique and b.is_unique and len(a) == len(b), "frozen paper membership duplicated or changed")
    order = a.get_indexer(b)
    require((order >= 0).all(), "graded paper row absent from frozen list")
    for column in PAPER_COLUMNS:
        require(_equal(frozen.iloc[order][column].reset_index(drop=True), graded[column].reset_index(drop=True)),
                "frozen paper field changed: " + column)
    require(set(graded.policy.unique()) <= set(POLICIES), "unregistered paper policy")
    require(not graded.duplicated(["policy"] + UNIT).any(), "policy selected multiple offers for one opportunity")
    require(graded.settlement.isin(STATES).all(), "unknown settlement encoding")
    require((np.isfinite(graded.decimal_odds) & graded.decimal_odds.gt(1)).all(), "invalid frozen selected price")
    matched_order = mi.get_indexer(_index(graded))
    require((matched_order >= 0).all(), "selected grade absent from matched offered packet")
    for column in ["actual", "participation_state", "outcome_state"]:
        require(_equal(matched.iloc[matched_order][column].reset_index(drop=True), graded[column].reset_index(drop=True)),
                "selected grade differs from the same matched offered row: " + column)
    for state in STATES:
        group = graded.loc[graded.settlement.eq(state)]
        if state == "unknown_ungraded":
            require(group.net_units.isna().all(), "unknown selected settlement was imputed")
        else:
            expected = group.decimal_odds - 1 if state == "assumed_win" else (-1 if state == "assumed_loss" else 0)
            require(np.isfinite(group.net_units).all() and np.allclose(group.net_units, expected, atol=1e-12, rtol=0),
                    "stored unit settlement contradicts its frozen state/price")
    return {"forecast_rows": len(forecasts), "matched_rows": len(matched), "frozen_selected_rows": len(frozen),
            "graded_selected_rows": len(graded), "no_forecasts_grades_or_selection_recomputed": True}


def common_packets(forecasts):
    """Exact predeclared denominator projection, before every policy EV screen.

    This repeats only the frozen common-population definition and its immutable
    68/69/79 book priority. It does not compute EV, pick a side or rerank a list.
    """
    eligible = forecasts.loc[forecasts[PROBABILITIES].notna().all(axis=1) & forecasts.F_point.notna() & forecasts.d_under.notna()]
    eligible = eligible.sort_values(UNIT + ["book_id", "source_collection_naive", "line", "source_row_number"], kind="stable")
    return eligible.drop_duplicates(UNIT)[OFFER + ["kickoff_utc"]].reset_index(drop=True)


def policy_packets(common, graded, policy):
    chosen = graded.loc[graded.policy.eq(policy)]
    require(_index(chosen).isin(_index(common)).all(), "paper selection outside frozen common opportunity packets")
    columns = OFFER + ["side", "decimal_odds", "settlement", "net_units"]
    packet = common.merge(chosen[columns], on=OFFER, how="left", validate="one_to_one", sort=False)
    packet["selected"] = packet.settlement.notna()
    packet["known"] = packet.selected & packet.settlement.ne("unknown_ungraded")
    packet["unknown"] = packet.selected & packet.settlement.eq("unknown_ungraded")
    packet["win"] = packet.settlement.eq("assumed_win")
    packet["loss"] = packet.settlement.eq("assumed_loss")
    packet["decisive"] = packet.win | packet.loss
    # A policy abstention has no stake or return. A selected unknown never gets
    # this zero-action value and remains missing in every paired packet.
    packet["packet_net"] = packet.net_units.where(packet.selected, 0.)
    return packet


def _statistics(packet):
    selected, known, unknown = packet.selected, packet.known, packet.unknown
    wins, losses = int(packet.win.sum()), int(packet.loss.sum())
    n, s, k, u = len(packet), int(selected.sum()), int(known.sum()), int(unknown.sum())
    net = float(packet.loc[known, "net_units"].sum()) if k or s == 0 else None
    selected_rows = packet.loc[selected]
    ordered = selected_rows.loc[selected_rows.known].sort_values(
        ["kickoff_utc", "game_id", "player_id", "target", "book_id", "line", "side"], kind="stable")
    if len(ordered):
        path = np.r_[0., ordered.net_units.to_numpy(float).cumsum()]
        drawdown = float(np.max(np.maximum.accumulate(path) - path))
    else:
        drawdown = 0. if s == 0 else None
    def average(mask):
        return float(packet.loc[mask, "decimal_odds"].mean()) if mask.any() else None
    return {"common_eligible_opportunities": n, "selected": s, "wins": wins, "losses": losses,
        "pushes_refunded": int(packet.settlement.eq("assumed_push_refund").sum()),
        "DNP_voids_refunded": int(packet.settlement.eq("assumed_DNP_void_refund").sum()), "unknown_ungraded": u,
        "all_selected_unit_stakes": s, "known_settled_unit_stakes_including_push_void_refunds": k,
        "decisive_unit_stakes": wins + losses, "unknown_ungraded_unit_stakes": u,
        "assumed_net_units_known_only": net, "known_net_is_partial": bool(u),
        "ROI_known_settled": _ratio(net, k) if net is not None else None,
        "ROI_decisive": _ratio(net, wins + losses) if net is not None else None,
        "hit_rate_wins_over_decisive": _ratio(wins, wins + losses),
        "mean_decimal_odds_selected": average(selected), "mean_decimal_odds_known_settled": average(known),
        "mean_decimal_odds_winning": average(packet.win), "selection_coverage": _ratio(s, n),
        "known_settlement_coverage": _ratio(k, s), "known_net_per_common_eligible_opportunity": _ratio(net, n) if net is not None else None,
        "known_path_max_drawdown_units": drawdown, "drawdown_is_partial": bool(u),
        "drawdown_order": "kickoffUTC,game/player/category/book/line/side; unknown omitted, not zero"}


def _bootstrap(packet, cluster):
    clusters = packet[cluster].drop_duplicates()
    if len(clusters) < 8:
        return {"state": "N_A_FEWER_THAN_8_CLUSTERS", "clusters": len(clusters), "replicates": 500, "seed": 1703}
    work = packet[[cluster]].copy()
    work["net"] = packet.net_units.where(packet.known, 0.)
    for name in ["selected", "known", "unknown", "win", "decisive"]:
        work[name] = packet[name].astype(int)
    work["opportunities"] = 1
    work["odds_selected"] = packet.decimal_odds.where(packet.selected, 0.)
    work["odds_known"] = packet.decimal_odds.where(packet.known, 0.)
    work["odds_win"] = packet.decimal_odds.where(packet.win, 0.)
    sums = work.groupby(cluster, observed=True, sort=True).sum()
    choice = np.random.default_rng(1703).integers(0, len(sums), size=(500, len(sums)))
    values = {column: sums[column].to_numpy(float)[choice].sum(axis=1) for column in sums}
    specs = {"assumed_net_units_known_only": ("net", None), "ROI_known_settled": ("net", "known"),
        "ROI_decisive": ("net", "decisive"), "hit_rate": ("win", "decisive"),
        "selection_coverage": ("selected", "opportunities"), "known_settlement_coverage": ("known", "selected"),
        "known_net_per_common_eligible_opportunity": ("net", "opportunities"),
        "mean_decimal_odds_selected": ("odds_selected", "selected"),
        "mean_decimal_odds_known_settled": ("odds_known", "known"), "mean_decimal_odds_winning": ("odds_win", "win")}
    intervals = {}
    for name, (numerator, denominator) in specs.items():
        valid = np.ones(500, bool) if denominator is None else values[denominator] > 0
        if numerator == "net":
            valid &= (values["known"] > 0) | (values["selected"] == 0)
        if not valid.all():
            intervals[name] = {"state": "N_A_UNDEFINED_RESAMPLED_DENOMINATOR_OR_UNGRADED_ONLY", "defined_replicates": int(valid.sum())}
        else:
            sampled = values[numerator] if denominator is None else values[numerator] / values[denominator]
            intervals[name] = {"state": "EXPOSED_SAMPLE_NOMINAL_INTERVAL", "lower95": float(np.quantile(sampled, .025)),
                               "upper95": float(np.quantile(sampled, .975))}
    return {"state": "WHOLE_CLUSTER_RATIO_SUM_BOOTSTRAP", "clusters": len(sums), "replicates": 500, "seed": 1703,
            "known_accounting_partial_if_unknown": bool(packet.unknown.any()), "intervals": intervals,
            "drawdown_CI": "NOT_REGISTERED_PATH_STATISTIC"}


def _paired(left, right):
    require(_index(left).equals(_index(right)), "paired policies require the same frozen common opportunity packets")
    valid = left.packet_net.notna() & right.packet_net.notna()
    difference = left.packet_net - right.packet_net
    net = float(difference.loc[valid].sum()) if valid.any() else None
    result = {"common_opportunities": len(left), "paired_known_packets": int(valid.sum()), "paired_unknown_packets": int((~valid).sum()),
              "paired_known_net_difference": net, "known_difference_per_all_common_opportunities": _ratio(net, len(left)) if net is not None else None,
              "known_difference_per_paired_known_packet": _ratio(net, int(valid.sum())) if net is not None else None,
              "partial_if_any_unknown": bool((~valid).any()), "paired_hit_rate_comparison": "NOT_USED_DIFFERENT_POLICY_HIT_POOLS"}
    for cluster in ["week", "game_id"]:
        count = left[cluster].nunique()
        if count < 8:
            ci = {"state": "N_A_FEWER_THAN_8_CLUSTERS", "clusters": int(count)}
        elif not valid.all():
            ci = {"state": "N_A_UNGRADED_PAIRED_PACKETS", "clusters": int(count)}
        else:
            group = pd.DataFrame({"cluster": left[cluster].to_numpy(), "net": difference.to_numpy(), "opportunities": 1}).groupby("cluster", sort=True).sum()
            picks = np.random.default_rng(1703).integers(0, len(group), size=(500, len(group)))
            sums = group.net.to_numpy()[picks].sum(axis=1)
            denoms = group.opportunities.to_numpy()[picks].sum(axis=1)
            ci = {"state": "EXPOSED_SAMPLE_NOMINAL_PAIRED_PACKET_INTERVAL", "clusters": len(group), "replicates": 500, "seed": 1703,
                  "net_difference_lower95": float(np.quantile(sums, .025)), "net_difference_upper95": float(np.quantile(sums, .975)),
                  "net_per_common_opportunity_difference_lower95": float(np.quantile(sums / denoms, .025)),
                  "net_per_common_opportunity_difference_upper95": float(np.quantile(sums / denoms, .975))}
        result["paired_" + cluster] = ci
    return result


def summarize_paper(forecasts, graded, categories):
    common = common_packets(forecasts)
    require(not graded.season.eq(2025).any(), "excluded season reached accounting")
    packets = {policy: policy_packets(common, graded, policy) for policy in POLICIES}
    summaries, comparisons = [], []
    for year in [2024, 2026]:
        for target in categories:
            at = common.season.eq(year) & common.target.eq(target)
            selected_packets = {policy: frame.loc[at].reset_index(drop=True) for policy, frame in packets.items()}
            for policy, packet in selected_packets.items():
                entry = {"season": year, "target": target, "policy": policy, **_statistics(packet),
                    "whole_week": _bootstrap(packet, "week"), "whole_game_secondary": _bootstrap(packet, "game_id"),
                    "weekly": [{"week": int(week), **_statistics(group)} for week, group in packet.groupby("week", sort=True, observed=True)]}
                summaries.append(entry)
            for a, b in itertools.combinations(POLICIES, 2):
                comparisons.append({"season": year, "target": target, "policy_A": a, "policy_B": b,
                                    **_paired(selected_packets[a], selected_packets[b])})
    return {"version": VERSION, "state": "FROZEN_LIST_ACCOUNTING_ONLY", "paper": summaries, "paired_common_opportunity_comparisons": comparisons,
        "common_eligible_opportunities": len(common), "all_frozen_selected_states": graded.settlement.value_counts().to_dict(),
        "qualification": "timing-unverified exploratory assumed settlement; no authenticated profitability, live or website-relative claim",
        "projectiongap_identity": "laboratory F point-gap proxy screened by frozen F probability and price; NOT actual website TopOver/Under",
        "stake": "one hypothetical unit per already selected offer; push and DNP void refund; unknown never imputed",
        "denominator_origin": "exact predeclared pre-EV population projection from immutable pre-outcome forecasts; no reranking/reselection",
        "interval_interpretation": "nominal exposed-history whole-cluster intervals; undefined bootstrap draws produce NA, never denominator replacement",
        "2026_week_uncertainty": "N_A_FEWER_THAN_8_CLUSTERS for five weeks; game secondary reported separately"}


def offered_coverage(matched):
    """Population support counts only; no new probability or football scoring."""
    records = []
    for (year, target), group in matched.groupby(["season", "target"], observed=True, sort=True):
        records.append({"season": int(year), "target": target, "offered_book_rows": len(group),
            "unique_player_game_category_opportunities": len(group[UNIT].drop_duplicates()),
            "primary_role_rows": int(group.primary_role.sum()), "outcome_states": group.outcome_state.value_counts(dropna=False).to_dict(),
            "supported_actual_rows": int((group.outcome_state.eq("supported_played") & group.actual.notna()).sum()),
            "frozen_point_available_rows": {arm: int(group[arm + "_point"].notna().sum()) for arm in ARMS},
            "frozen_probability_available_rows": {name: int(group[name].notna().sum()) for name in PROBABILITIES}})
    return records


def write_readable_csv(stream, matched, graded, *, model_bindings, packet_bindings, names=None):
    """Write all matched offered rows with only frozen values and derived errors."""
    names = names or {}
    present = [column for column in MATCHED_COLUMNS if column in matched]
    errors = [arm + suffix for arm in ARMS for suffix in ["_error", "_absolute_error"]]
    flags = [policy + suffix for policy in POLICIES for suffix in ["_selected", "_selected_side", "_settlement", "_net_units"]]
    extra = ["display_name", "F_model_sha256", "calibration_packet_sha256", "forecast_packet_sha256", "matched_scores_packet_sha256"]
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(present + errors + flags + extra)
    lookup = {(row.policy,) + tuple(getattr(row, c) for c in OFFER): row for row in graded.itertuples(index=False)}
    # Display order only: current season first, then the earlier evaluation
    # season; frozen membership, values and policy selections are unchanged.
    ordered = matched.sort_values(["season", "week", "kickoff_utc", "game_id", "player_id", "target", "book_id"],
                                 ascending=[False, True, True, True, True, True, True], kind="stable")
    for values in ordered[present].itertuples(index=False, name=None):
        row = dict(zip(present, values))
        error_values = []
        actual = row.get("actual")
        supported = row.get("outcome_state") == "supported_played" and pd.notna(actual)
        for arm in ARMS:
            value = row.get(arm + "_point")
            error = float(value - actual) if supported and pd.notna(value) else None
            error_values.extend([error, abs(error) if error is not None else None])
        selected_values = []
        key = tuple(row[c] for c in OFFER)
        for policy in POLICIES:
            pick = lookup.get((policy,) + key)
            selected_values.extend([pick is not None, pick.side if pick else None,
                                    pick.settlement if pick else None, pick.net_units if pick else None])
        model_year = row.get("F_model_year")
        model = model_bindings.get(str(int(model_year)), {}).get(row["target"], {}) if pd.notna(model_year) else {}
        sha = model.get("model.joblib", {}).get("sha256", "")
        extras = [names.get((int(row["season"]), int(row["week"]), row["player_id"]), ""), sha,
                  packet_bindings["calibrators"], packet_bindings["forecasts"], packet_bindings["matched"]]
        output = list(values) + error_values + selected_values + extras
        writer.writerow(["" if value is None or (not isinstance(value, str) and pd.isna(value)) else value for value in output])
    return len(matched)
