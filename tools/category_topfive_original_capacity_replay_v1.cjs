'use strict';
// Exposed descriptive capacity replay. Never replaces original recommendations.
function run(inputs, records) {
  const states=['hit','miss','push','dnp','pending','unresolved','excluded'];
  const tally=a=>{const r=Object.fromEntries(states.map(k=>[k,0]));for(const x of a)r[x.result]++;r.decided=r.hit+r.miss;r.hit_rate=r.decided?r.hit/r.decided:null;return r;};
  const policies=[['TOP_6_ORIGINAL_SCORE',6,0],['TOP_10_ORIGINAL_SCORE',10,0],['TOP_20_ORIGINAL_SCORE',20,0],['TOP_20_ABSTAIN_ABS_SCORE_AT_LEAST_2',20,2]];
  const weekly=[],selections=[];
  for(const [policy,capacity,minscore]of policies)for(const {archive:a}of inputs.weeks){
    const keys=new Set(),pool=[];
    for(const side of ['over','under'])for(const q of a.picks[side]||[]){
      const r=records.find(r=>r.cohort==='ORIGINAL_TOP_PICKS'&&r.week===a.week&&r.player_id===q.player_id&&r.game_id===q.game_id&&r.category===q.key&&r.side===side&&r.line===q.line);
      if(!r||r.result==='excluded'||typeof q.score!=='number')continue;
      const key=[a.week,q.game_id,q.player_id,q.key].join('|');if(keys.has(key))throw Error('Duplicate primary offer');keys.add(key);
      pool.push({...r,score:q.score,tie:[q.game_id,q.player_id,q.key,side,q.line].join('|')});
    }
    pool.sort((a,b)=>Math.abs(b.score)-Math.abs(a.score)||a.tie.localeCompare(b.tie));
    const selected=pool.filter(x=>Math.abs(x.score)>=minscore).slice(0,capacity);
    selections.push(...selected.map(x=>({...x,policy})));
    const control=side=>tally(selected.map(x=>({...x,result:['hit','miss'].includes(x.result)&&x.side!==side?(x.result==='hit'?'miss':'hit'):x.result})));
    weekly.push({policy,week:a.week,eligible_original_highlighted_pool:pool.length,selected:selected.length,abstained:pool.length-selected.length,capacity,minimum_abs_score:minscore,
      controls:{original:tally(selected),always_over:control('over'),always_under:control('under')},
      by_category:[...new Set(selected.map(x=>x.category))].sort().map(category=>({category,over:tally(selected.filter(x=>x.category===category&&x.side==='over')),under:tally(selected.filter(x=>x.category===category&&x.side==='under'))}))});
  }
  return {version:'original-highlighted-pool-capacity-replay-v1',protocol:'TOP_CAPACITY_REPLAY_PROTOCOL_V1.json',source_commit:inputs.commit,
    evidence_tier:'EXPOSED_DESCRIPTIVE_REPLAY_OF_ORIGINAL_HIGHLIGHTED_POOL',new_original_recommendations:false,new_fits:0,new_forecasts:0,
    probabilities:null,prices:null,returns:null,reason:'Original archive rows have no supported probability law or compatible price/settlement vector.',
    limitation:'Original highlighted pool was already selected with side-specific lists; these are capacity replays of that retained pool, not a full-board or prospectively tested strategy. Do not replace original saved recommendations.',
    cumulative:policies.map(([policy])=>{const a=selections.filter(x=>x.policy===policy);return {policy,selected:a.length,unique_games:new Set(a.map(x=>x.game_id)).size,over:tally(a.filter(x=>x.side==='over')),under:tally(a.filter(x=>x.side==='under')),overall:tally(a),weeks:[4,5,6,7,8],pending_week8:true};}),weekly};
}
module.exports={run};
if(require.main===module){const fs=require('fs');fs.writeFileSync(process.argv[4],JSON.stringify(run(JSON.parse(fs.readFileSync(process.argv[2],'utf8')),JSON.parse(fs.readFileSync(process.argv[3],'utf8'))))+'\n');}
