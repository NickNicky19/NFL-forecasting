'use strict';
// Scores original archived sides. Does not choose or replace recommendations.
const CATEGORIES = ['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec_tgt','rec','rec_yd','rush_rec_yd','fpts','anytime_td'];
const VERSION = 'original-recorded-leans-report-v1';
const GRADING = 'statistical-v3-identity-20261025';
function canonical(x) {
  if (Array.isArray(x)) return '['+x.map(canonical).join(',')+']';
  if (x && typeof x==='object') return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}';
  return JSON.stringify(x);
}
function number(x) {return typeof x==='number' && Number.isFinite(x);}
function identityEntry(a,p,e) {
  if (!e || typeof e!=='object') return null;
  const gs=a.games.filter(g=>g.id===p.game_id);
  if(gs.length!==1) return null;
  const g=gs[0], opp=p.team===g.home?g.away:p.team===g.away?g.home:null;
  if(!opp || (p.opp && p.opp!==opp) || (e.team && e.team!==p.team) || (e.opp && e.opp!==opp)) return null;
  return e;
}
function outcome(a,p,q,stats,finals) {
  if(p.late) return {result:'excluded',reason:'ORIGINAL_LATE_FLAG'};
  if(!finals.has(p.game_id)) return {result:'pending',reason:'NOT_IN_PUBLISHED_FINAL_GAME_SCOPE'};
  const e=identityEntry(a,p,stats[p.id]);
  if(!e) return {result:'unresolved',reason:'MISSING_OR_CONTRADICTORY_OUTCOME_IDENTITY'};
  const s=e.stats||{}, played=(s.gp||0)>0 || (s.off_snp||0)>0;
  const dnp=e.participation_status==='dnp' && !!e.participation_source;
  if(played&&dnp) return {result:'unresolved',reason:'CONTRADICTORY_PARTICIPATION'};
  if(dnp) return {result:'dnp',reason:'ATTRIBUTED_DNP_NOT_ASSUMED_VOID'};
  if(!played) return {result:'unresolved',reason:'UNKNOWN_PARTICIPATION'};
  // Same legacy compact-stat convention as the pinned grader, only after played evidence.
  const v=k=>s[k]===undefined || s[k]===null?0:s[k];
  const raw=q.key==='rush_rec_yd'?v('rush_yd')+v('rec_yd'):v(q.key);
  if(!number(raw)||!number(q.line)) return {result:'unresolved',reason:'NONFINITE_ACTUAL_OR_LINE'};
  const y=Math.round((raw+Number.EPSILON)*100)/100;
  const result=y===q.line?'push':(q.lean==='over'?y>q.line:y<q.line)?'hit':'miss';
  return {result,actual:y,absolute_error:number(q.adj)?Math.abs(q.adj-y):null,
    statistical_direction:y===q.line?'EXACT_LINE':y>q.line?'ABOVE_LINE':'BELOW_LINE',
    settlement:'UNVERIFIED_NO_VENUE_CONTRACT'};
}
function rng(seed){let s=seed>>>0;return()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};}
function interval(rs,field,seed) {
  const groups=new Map();
  for(const r of rs.filter(r=>r.result==='hit'||r.result==='miss')) {
    const k=String(r[field]); if(!groups.has(k))groups.set(k,[0,0]);
    groups.get(k)[r.result==='hit'?0:1]++;
  }
  const g=[...groups.values()];
  if(g.length<2) return {low:null,high:null,clusters:g.length,reason:'FEWER_THAN_TWO_DECISIVE_CLUSTERS'};
  const random=rng(seed), samples=[];
  for(let i=0;i<1000;i++){let h=0,m=0;for(let j=0;j<g.length;j++){const x=g[Math.floor(random()*g.length)];h+=x[0];m+=x[1];}if(h+m)samples.push(h/(h+m));}
  samples.sort((a,b)=>a-b);
  return {low:samples[Math.floor(samples.length*.025)],high:samples[Math.min(samples.length-1,Math.floor(samples.length*.975))],clusters:g.length,replicates:1000,seed,interpretation:'DESCRIPTIVE_UNADJUSTED_NOT_SELECTED_POLICY_GUARANTEE'};
}
function tally(rs,seed) {
  const r={hit:0,miss:0,push:0,void:0,dnp:0,pending:0,unresolved:0,excluded:0};
  for(const x of rs)r[x.result]++;
  r.decided=r.hit+r.miss;r.hit_rate=r.decided?r.hit/r.decided:null;
  r.observed_decisions=rs.length;
  r.game_cluster_interval=interval(rs,'game_id',seed);
  r.week_cluster_interval=interval(rs,'week',seed);
  const err=rs.filter(x=>number(x.absolute_error)).map(x=>x.absolute_error);
  r.point_MAE=err.length?err.reduce((a,b)=>a+b,0)/err.length:null;
  r.point_MAE_n=err.length;
  r.probability_score=null;r.probability_score_reason='ORIGINAL_ROWS_HAVE_NO_AUTHENTICATED_OUTCOME_LAW';
  r.paper_return=null;r.paper_return_reason='COMPATIBLE_ORIGINAL_PRICES_AND_SETTLEMENT_NOT_RETAINED';
  return r;
}
function provenance(q,p) {
  const model=q.model_version||q.reference_model||p.model_version||p.reference_model||null;
  const policy=q.selection_policy_version||q.policy_version||p.selection_policy_version||null;
  const src=q.forecast_source||p.forecast_source||null;
  return {model_version:model||'UNKNOWN_LEGACY_ATTRIBUTION',selection_policy_version:policy||'UNKNOWN_ORIGINAL_POLICY_VERSION',
    provenance:src|| (model?'EXPLICIT_RECORDED_REFERENCE_NOT_AUTOMATIC_R0':'UNKNOWN_LEGACY_ATTRIBUTION')};
}
function report(inputs) {
  const records=[], seen=new Map(), duplicate=[], collisions=[], population=[];
  for(const item of inputs.weeks) {
    const a=item.archive, stats=item.stats, finals=new Set(item.final_games), src=item.published_week;
    const players=new Map(a.players.map(p=>[p.id,p]));
    let offers=0, leanCount=0, synthetic=0, noSide=0;
    function add(p,q,cohort) {
      if(!['over','under'].includes(q.lean)|| !['dk','sleeper'].includes(q.line_from)|| q.key==='anytime_td')return;
      const key=[a.season,a.week,cohort,p.id,p.game_id,q.key,q.lean,q.line].join('|');
      const payload=canonical({p:{id:p.id,team:p.team,opp:p.opp,game_id:p.game_id,late:p.late},q});
      if(seen.has(key)){if(seen.get(key)===payload)duplicate.push(key);else collisions.push(key);return;}
      seen.set(key,payload);
      const pr=provenance(q,p), grade=outcome(a,p,q,stats,finals);
      records.push({season:a.season,week:a.week,cohort,category:q.key,game_id:p.game_id,player_id:p.id,
        line:q.line,side:q.lean,line_from:q.line_from,...pr,...grade,archive_saved_at:a.saved_at,
        evidence_tier:'ORIGINAL_SAVED_SIDE_ORIGINAL_LINE_TIMING_LIMITED',partial_week:!src.complete,
        forecast_time:null,forecast_time_reason:'ARCHIVE_SAVED_AT_IS_NOT_PER_ROW_ORIGINAL_ISSUE_TIME',
        quote_time:null,quote_time_reason:'ORIGINAL_QUOTE_TIMESTAMP_NOT_RETAINED',price:null,
        point:number(q.adj)?q.adj:null,point_product:'LEGACY_ADJUSTED_EMPIRICAL_POINT_NOT_NEW_MAE_PROFILE'});
    }
    for(const p of a.players)for(const q of p.props||[]){
      if(['dk','sleeper'].includes(q.line_from)){offers++;if(q.lean){leanCount++;add(p,q,'ALL_RECORDED_LEANS');}else noSide++;}
      else if(q.lean)synthetic++;
    }
    for(const side of ['over','under'])for(const q of a.picks[side]||[]){
      const p=players.get(q.player_id);
      if(p && p.game_id===q.game_id)add(p,{...q,lean:side},'ORIGINAL_TOP_PICKS');
      else records.push({season:a.season,week:a.week,cohort:'ORIGINAL_TOP_PICKS',category:q.key,side,game_id:q.game_id,player_id:q.player_id,
        ...provenance(q,{}),result:'unresolved',reason:'ORIGINAL_PICK_PLAYER_GAME_IDENTITY_MISMATCH',partial_week:!src.complete});
    }
    population.push({season:a.season,week:a.week,archive_player_rows:a.players.length,original_real_line_rows:offers,original_real_line_leans:leanCount,
      real_lines_without_lean:noSide,excluded_nonbook_lean_rows:synthetic,archive_saved_at:a.saved_at,published_games_complete:src.games_complete,
      published_fully_resolved:src.complete,final_game_ids:item.final_games,final_scope_source:item.final_scope_source});
  }
  if(collisions.length)throw new Error('Original decision identity/content collisions require a versioned adjudication: '+collisions.length);
  function row(rs,category,cohort,week,byVersion) {
    const models=[...new Set(rs.map(x=>x.model_version))],policies=[...new Set(rs.map(x=>x.selection_policy_version))];
    return {category,cohort,season:2026,week,model_version:models.length===1?models[0]:models.length?'MIXED_ORIGINAL_PROVENANCE':'NOT_AVAILABLE',
      selection_policy_version:policies.length===1?policies[0]:policies.length?'MIXED_ORIGINAL_POLICIES':'NOT_AVAILABLE',
      provenance:byVersion?rs[0]?.provenance||'NOT_AVAILABLE':'SEE_ORIGINAL_VERSION_BREAKDOWN',
      evidence_tier:'ORIGINAL_SAVED_SIDE_ORIGINAL_LINE_TIMING_LIMITED',over:tally(rs.filter(x=>x.side==='over'),20261030),
      under:tally(rs.filter(x=>x.side==='under'),20261030),unique_games:new Set(rs.map(x=>x.game_id)).size,
      unique_player_games:new Set(rs.map(x=>x.player_id+'|'+x.game_id)).size,
      weeks:[...new Set(rs.map(x=>x.week))].sort((a,b)=>a-b),partial_weeks:[...new Set(rs.filter(x=>x.partial_week).map(x=>x.week))].sort((a,b)=>a-b),
      unsupported_reason:rs.length?null:category==='rec_tgt'?'TARGET_OFFER_UNAVAILABLE':category==='fpts'?'NO_ORIGINAL_AUTHENTIC_CHART_PPR_OFFER':category==='anytime_td'?'NO_COMPATIBLE_ORIGINAL_EVENT_OFFER':'NO_ORIGINAL_QUALIFYING_LEAN_OR_PICK'};
  }
  const cumulative=[],weekly=[],by_version=[];
  for(const cohort of ['ALL_RECORDED_LEANS','ORIGINAL_TOP_PICKS'])for(const category of CATEGORIES){
    const rs=records.filter(x=>x.cohort===cohort&&x.category===category);
    cumulative.push(row(rs,category,cohort,null,false));
    for(const w of inputs.weeks.map(x=>x.archive.week))weekly.push(row(rs.filter(x=>x.week===w),category,cohort,w,false));
    const versions=[...new Set(rs.map(x=>canonical([x.model_version,x.selection_policy_version,x.provenance])))];
    for(const v of versions)by_version.push(row(rs.filter(x=>canonical([x.model_version,x.selection_policy_version,x.provenance])===v),category,cohort,null,true));
  }
  const all=records.filter(x=>x.cohort==='ALL_RECORDED_LEANS');
  const over=tally(all.filter(x=>x.side==='over'),20261030),under=tally(all.filter(x=>x.side==='under'),20261030);
  const reconciliation={published:{over:inputs.track.cumulative.dk_leans.over,under:inputs.track.cumulative.dk_leans.under},computed:{over,under},
    exact_side_hits_and_misses:over.hit===394&&over.miss===397&&under.hit===349&&under.miss===236,
    category_quoted_denominator:'The quoted 53/75,38/61,221/363,35/58 are hits/decided, NOT hits/misses.',category_checks:{}};
  for(const cat of ['pass_td','pass_cmp','rec','pass_att']){
    const rs=all.filter(x=>x.category===cat),v=tally(rs,20261030),p=inputs.track.cumulative.leans.by_category[cat];
    reconciliation.category_checks[cat]={hit:v.hit,miss:v.miss,decided:v.decided,published:p,exact:v.hit===p.hit&&v.miss===p.miss&&v.decided===p.n_decided};
  }
  const output={schema_version:VERSION,source:{snapshot_commit:inputs.commit,grading_version:GRADING,original_side_fields:['players[].props[].lean','picks.over[]','picks.under[]'],
      venue_settlement:'STATISTICAL_ONLY_NOT_VENUE_VERIFIED',source_manifest:inputs.source_manifest},tables:{cumulative,weekly,by_version},reconciliation,population,
    duplicate_policy:{rule:'Only identical original decision content at identical season/week/cohort/player/game/category/side/line is collapsed; conflicts fail.',identical_duplicates:duplicate.length,collisions:collisions.length},
    limitations:['These are original saved sides at original lines, not newly inferred sides or probability forecasts.',
      'Archive save clocks do not prove each original issue or quote was pregame. Late flags are excluded and retained as exclusions; legacy unflagged timing remains limited.',
      'Ordinary legacy archives do not retain complete method/policy IDs. Missing provenance stays unknown; sparse explicit references are preserved.',
      'Existing grader compact-stat zero convention is reused only with positive played evidence; this is not new independent complete label qualification.',
      'Game/week intervals are descriptive, unadjusted and may be unstable for small samples; overlapping targets are not independent games.',
      'Week 8 is in progress; Weeks 6/7 have unresolved outcomes despite all games being complete.',
      'Prices, venue rules, calibrated probability laws and actual new MAE recommendations are absent; no ROI, EV or probability improvement is established.',
      'Selected-ranking companions are a separate provenance stream; legacy archive Top Picks do not automatically represent that newer ranking policy.']};
  return {public_report:output,private_scorecard:records};
}
module.exports={VERSION,report};
if(require.main===module){const fs=require('fs');const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const r=report(input);fs.writeFileSync(process.argv[3],JSON.stringify(r.public_report,null,2)+'\n');if(process.argv[4])fs.writeFileSync(process.argv[4],JSON.stringify(r.private_scorecard)+'\n');}
