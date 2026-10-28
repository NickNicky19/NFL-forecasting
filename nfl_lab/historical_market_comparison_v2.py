"""Technical continuation: cached offers and exact-context row abstentions.

The V1 comparison/formula implementation is imported unchanged. No old forecast
input, model, source vector, failed receipt or scientific parameter is edited.
"""
from __future__ import annotations

import hashlib
import json

from . import historical_market_comparison as core

VERSION = "historical-market-comparison-no2025-technical-v2-20261028"


def eligible_contexts(plan, offers, budget):
    """Match metadata only, retain conflicts, and let V1 recheck every survivor.

    Original football role is evidence for the model contract, not an update to
    the source role. Conflicts abstain; neither role nor frozen feature values
    are rewritten. 2026 metadata is projected from the same primitive container
    used by the unchanged V1 no2025 feature builder.
    """
    import numpy as np
    import pandas as pd
    import pyarrow.dataset as ds
    keys = core.KEYS
    context = ["team", "opponent", "position", "kickoff_utc"]
    qualified, abstained, audits = [], [], []
    for year in [2026, 2024, 2023, 2022]:
        selected = offers.loc[offers.season.eq(year)].copy().reset_index(drop=True)
        if selected.empty:
            audits.append({"year": year, "offered": 0, "compatible": 0, "abstained": 0})
            continue
        if year == 2026:
            dataset = ds.dataset(core.authenticate(plan["raw_primitive_container"]), format="parquet")
            query = dataset.to_table(columns=keys + context,
                filter=(ds.field("season") == 2026) & ds.field("week").isin([1, 2, 3, 4, 5])).to_pandas()
        else:
            query = pd.read_parquet(core.authenticate(plan["historical_queries"][str(year)]), columns=keys + context)
        budget.check("context_metadata_rows", len(query))
        core.require(not query.season.eq(2025).any() and not query.duplicated(keys).any(), "forbidden/ambiguous context metadata")
        renamed = query.rename(columns={c: "original_football_" + c for c in context})
        merged = selected.merge(renamed, on=keys, how="left", validate="many_to_one", sort=False, indicator=True)
        core.require(len(merged) == len(selected), "context qualification changed offer count")
        missing = merged["_merge"].ne("both")
        reasons = pd.Series("", index=merged.index, dtype=object)
        reasons.loc[missing] = "missing_original_football_query_context"
        differences = {}
        for name in context:
            left, right = merged[name], merged["original_football_" + name]
            if name.endswith("_utc"):
                equal = pd.to_datetime(left, utc=True).eq(pd.to_datetime(right, utc=True))
            else:
                equal = left.astype(str).eq(right.astype(str))
            bad = ~missing & (~equal | left.isna() | right.isna())
            differences[name] = int(bad.sum())
            prefix = reasons.loc[bad].where(reasons.loc[bad].eq(""), reasons.loc[bad] + ";")
            reasons.loc[bad] = prefix + "context_mismatch_" + name
        good = reasons.eq("")
        qualified.append(selected.loc[good].copy())
        rejected = merged.loc[~good].drop(columns="_merge").copy()
        rejected["context_abstention_reasons"] = reasons.loc[~good]
        rejected["source_role_retained"] = rejected.position
        rejected["original_football_role_retained"] = rejected.original_football_position
        rejected["context_policy"] = "STRICT_ABSTENTION_NO_ROLE_OR_FEATURE_REWRITE"
        abstained.append(rejected)
        primary_source, primary_football = np.zeros(len(merged), bool), np.zeros(len(merged), bool)
        for target, contract in plan["category_dependencies"].items():
            at = merged.target.eq(target)
            primary_source[at] = merged.loc[at, "position"].isin(contract["primary_roles"])
            primary_football[at] = merged.loc[at, "original_football_position"].isin(contract["primary_roles"])
        audits.append({"year": year, "offered": len(selected), "compatible": int(good.sum()), "abstained": int((~good).sum()),
            "missing_original_query_context": int(missing.sum()), "context_mismatch_counts": differences,
            "abstained_source_role_counts": rejected.position.value_counts(dropna=False).to_dict(),
            "abstained_original_football_role_counts": rejected.original_football_position.value_counts(dropna=False).to_dict(),
            "source_primary_role_offers": int(primary_source.sum()), "original_football_primary_role_offers": int(primary_football.sum()),
            "compatible_primary_role_offers": int((primary_source & good.to_numpy()).sum()),
            "source_versus_original_role_is_not_resolved_or_reclassified": True})
        budget.check()
    core.require(qualified, "no compatible context rows; preserve whole offered pool and abstentions")
    compatible = pd.concat(qualified, ignore_index=True)
    abstentions = pd.concat(abstained, ignore_index=True) if abstained else offers.iloc[:0].copy()
    core.require(len(compatible) + len(abstentions) == len(offers), "offered pool membership lost during context abstention")
    return compatible, abstentions, audits
