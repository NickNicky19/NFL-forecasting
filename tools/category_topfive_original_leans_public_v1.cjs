'use strict';
// Serialization-only projection; preserves every actual grade and denominator.
function compact(report, records) {
  const d=JSON.parse(JSON.stringify(report));
  d.metric_support={probability_score:null,probability_score_reason:'Original rows have no authenticated predictive law.',paper_return:null,paper_return_reason:'Compatible original prices and venue contracts are missing.'};
  d.resampling={replicates:1000,seed:20261030,interpretation:'Descriptive unadjusted game/week cluster bootstrap; not a selected-policy guarantee.'};
  const lists=Object.values(d.tables);
  for(const list of lists)for(const row of list)for(const side of ['over','under']){
    const v=row[side];
    for(const k of ['probability_score','probability_score_reason','paper_return','paper_return_reason'])delete v[k];
    for(const key of ['game_cluster_interval','week_cluster_interval'])if(v[key])for(const k of ['replicates','seed','interpretation'])delete v[key][k];
  }
  d.weekly_unsupported_rows='Empty weekly category/cohort cells are omitted; all thirteen targets and unsupported reasons remain in cumulative coverage.';
  d.tables.weekly=d.tables.weekly.filter(row=>row.over.observed_decisions+row.under.observed_decisions>0);
  if (records) for (const [view,list] of Object.entries(d.tables)) for (const row of list) {
    const selected=records.filter(x=>x.category===row.category&&x.cohort===row.cohort&&(row.week===null||x.week===row.week)
      &&(view!=='by_version'||x.model_version===row.model_version&&x.selection_policy_version===row.selection_policy_version&&x.provenance===row.provenance));
    const decided=selected.filter(x=>x.result==='hit'||x.result==='miss');
    row.unique_decisive_games=new Set(decided.map(x=>x.game_id)).size;
    row.unique_decisive_player_games=new Set(decided.map(x=>x.player_id+'|'+x.game_id)).size;
  }
  d.coverage_field_definitions={unique_games:'All original recorded opportunities, including pending and excluded late rows.',unique_decisive_games:'Games with at least one statistical hit or miss in this row.',unique_decisive_player_games:'Distinct player/game identities among statistical hits and misses; multiple categories are not independent football observations.'};
  for(const side of ['over','under']){
    const v=d.reconciliation.computed[side];
    v.point_MAE=null;v.point_MAE_n=null;v.point_MAE_reason='INCOMPATIBLE_STAT_UNITS_POOLED; category-specific point MAEs remain separate.';
    for(const k of ['probability_score','probability_score_reason','paper_return','paper_return_reason'])delete v[k];
  }
  d.representation_version='public-compact-v1';
  return d;
}
module.exports={compact};
