'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
let checks=0;const req=(v,s)=>{checks++;assert(v,s);};
const source=input.app,board=input.board,doc=input.overlay;
req(doc.rows.length===1948,'exact active release1948');req(board.games.every(g=>g.state==='pre'),'allactualgamespregame');
const now=Date.parse(input.observed_at);class Clock extends Date{static now(){return now;}}
const ctx={Date:Clock,TextEncoder,crypto:webcrypto,module:{exports:{}},console:{log(){},warn(){},error(){}},fetch(){throw Error('VM network forbidden');}};
vm.createContext(ctx);new vm.Script(input.helper,{filename:'actual-served-weekly-adaptive-overlay.js'}).runInContext(ctx,{timeout:5000});
const helper=ctx.module.exports;req(typeof helper.validate==='function'&&typeof helper.card==='function','actual served helper exports');ctx.WeeklyAdaptiveOverlay=helper;
const overlay=helper.validate(doc,board,input.board_sha256);req(overlay.rows.size===1948,'actual served overlay validated');
const extract=name=>{const found=source.match(new RegExp('(?:async )?function '+name+'\\([^]*?\\n\\}'));req(!!found,'actual served '+name);return found[0];};
const names=['selectedRankingPolicy','rankingCanonical','selectedPropForecast','effectivePropForecast','selectedPropGap','selectedPlayerGap','visibleTopPicks','compareSelectedRankingItems','validateSelectedRankings','filteredPlayers','propStatus','pv','propChip','pickCard','topPicksSourceCaption','renderProps'];
const constants=['SHORT','LINE_FROM','LINE_TAG','esc','fmt'].map(name=>{const pat=name==='SHORT'?/const SHORT = \{[^]*?\n\};/:new RegExp('const '+name+' = [^\\n]+');const found=source.match(pat);req(!!found,'actual served constant '+name);return found[0];}).join('\n');
const main={innerHTML:''};
const S={data:board,weeklyOverlay:overlay,selectedRankings:null,byId:Object.fromEntries(board.players.map(p=>[p.id,p])),games:Object.fromEntries(board.games.map(g=>[g.id,g])),lines:{},favs:new Set(),shown:0,sc:{half:false},f:{sort:'selected_edge',cat:'',q:'',pos:'ALL',game:'',hideOut:false,favs:false}};
Object.assign(ctx,{S,UNAVAILABLE:new Set(),normName:x=>String(x??'').toLowerCase(),posMatch:(p,f)=>f==='ALL'||p===f,injOf:p=>({status:p.injury||''}),projPts:p=>p.proj_ppr,livePPR:()=>null,isDefault:()=>true,$:x=>{req(x==='#main','onlysyntheticmainDOM');return main;},store:()=>true,withFlex:x=>x,playerCard:()=>'',avatar:()=>'',injBadge:()=>'',oppText:()=>'',liveLineText:()=>'',progress:()=>'',minePick:()=>false,gameStatus:()=>'Pregame',fmtStat:(k,v)=>String(v),resBadge:()=>''});
new vm.Script(constants+'\n'+names.map(extract).join('\n'),{filename:'actual-served-app-consumer-functions.js'}).runInContext(ctx,{timeout:5000});
(async()=>{
 const validated=await ctx.validateSelectedRankings(input.ranking,input.ranking_pointer,board,overlay);S.selectedRankings=validated;
 const lookup=new Map(board.players.map(p=>[p.game_id+'|'+p.id,p])),counts={},products={},labels={};let chip=0;
 for(const row of doc.rows){
  const p=lookup.get(row.game_id+'|'+row.player_id);req(!!p,'playerexists');const prop=p.props.find(x=>x.key===row.category);req(!!prop,'propexists');
  const got=ctx.selectedPropForecast(p,row.category);req(got&&got.value===row.forecast_value,'actual card numericbinding');const effective=ctx.effectivePropForecast(p,prop);req(effective.source==='SELECTED'&&effective.value===row.forecast_value,'effective selected source');
  const expectedLabel={point_mean:'mean',point_median:'median',binary_probability:'TD probability'}[row.product];req(got.label===expectedLabel,'correct functional label');
  const text=row.product==='binary_probability'?(100*row.forecast_value).toFixed(1)+'%':row.forecast_value.toFixed(2);req(got.text===text,'actual numeric display formatting');
  const html=ctx.propChip(p,prop);req(html.includes('data-weekly-primary')&&html.includes('<b>'+text+'</b>')&&html.includes(expectedLabel),'actual prop-chip rendered savednumber+product');chip++;
  counts[row.category]=(counts[row.category]||0)+1;products[row.product]=(products[row.product]||0)+1;labels[expectedLabel]=(labels[expectedLabel]||0)+1;
 }
 const sorting={};
 for(const category of Object.keys(counts)){
  S.f.cat=category;S.f.sort='selected_value';const list=ctx.filteredPlayers();let previous=Infinity,available=0;for(const p of list){const row=ctx.selectedPropForecast(p,category);const score=row?row.value:-Infinity;req(score<=previous,'actual selected-highest descending; unavailablelast');previous=score;available+=!!row;}sorting[category]={mode:'selected_value',selected_rows:available,descending:true};
 }
 S.f.cat='';S.f.sort='selected_edge';const list=ctx.filteredPlayers();let previous=Infinity;for(const p of list){const score=ctx.selectedPlayerGap(p);req(score<=previous,'actual biggestgap descending');previous=score;}
 const top={};for(const side of['over','under']){
  const items=ctx.visibleTopPicks(side);req(items.length===input.ranking.picks[side].length,'visible list membership matches validated savedranking');let selected=0,fallback=0;
  for(const pick of items){const html=ctx.pickCard(pick);req(html.includes('class="pick"'),'actual pick-card templateproduced');if(pick.forecast_source==='SELECTED'){const row=overlay.rows.get(JSON.stringify([pick.game_id,pick.player_id,pick.key]));req(row&&row.forecast_value===pick.adj,'top saved selected value');req(html.includes('Selected '+(pick.product==='point_mean'?'mean':'median')),'top product label');selected++;}else fallback++;}
  top[side]={rows:items.length,selected,fallback,caption:ctx.topPicksSourceCaption(items)};
 }
 const fantasy=board.players.flatMap(p=>p.props.filter(x=>x.key==='fpts').map(x=>({p,x})));req(fantasy.every(({p})=>ctx.selectedPropForecast(p,'fpts')===null),'old PPR never silentlyselected/migrated');
 ctx.renderProps();req(main.innerHTML.includes('Sort: New forecasts: biggest gap')&&main.innerHTML.includes('Sort: New forecast: highest'),'actual render menuoptions');req(main.innerHTML.includes('Top Overs')&&main.innerHTML.includes('Top Unders'),'actual top sections');req(main.innerHTML.includes('not win probabilities or expected returns'),'truthful gap explanation');
 console.log(JSON.stringify({state:'PASS_ACTUAL_SERVED_CONSUMER_VALUES_SORT_AND_RENDER_TEMPLATES',checks,selected_rows:1948,prop_chips_checked:chip,categories:counts,products,labels,highest_sort:sorting,biggest_gap_sort:true,top,old_contract_fantasy_rows:fantasy.length,old_PPR_selected:false,synthetic_main_HTML_bytes:Buffer.byteLength(main.innerHTML),full_browser_or_device_layout_test:false,scope:'Actualservedboundfunctions/realpublicinputs; syntheticDOM/cosmeticstubs; no browserlayout/MyPicksstoragevalidation; no newforecast,accuracygradeorNFLobservation'}));
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;});
