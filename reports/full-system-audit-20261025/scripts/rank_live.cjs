'use strict';
const {chromium}=require('playwright');const fs=require('fs');
const root=process.env.NFL_AUDIT_ROOT||__dirname,base='https://nicknicky19.github.io/nicks-expert-nfl-picks/';
(async()=>{
 const opts={executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']};
 if(process.env.HTTPS_PROXY)opts.proxy={server:process.env.HTTPS_PROXY};
 const browser=await chromium.launch(opts),scenes=[];
 try{for(const width of [320,390,1280]){
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'#/props',{waitUntil:'domcontentloaded',timeout:60000});
  await page.waitForFunction(()=>typeof S!=='undefined'&&S.selectedRankings,{timeout:30000});
  const top=await page.evaluate(()=>{
   const doc=S.selectedRankings,groups=[...document.querySelectorAll('.picks-wrap > .picks')];
   const result={};
   for(const [i,side] of ['over','under'].entries()){
    const expected=doc.picks[side],actual=[...groups[i].querySelectorAll('.pick[data-open]')].map(n=>n.dataset.open);
    if(JSON.stringify(actual)!==JSON.stringify(expected.map(p=>p.player_id)))throw Error('Top membership/order mismatch');
    for(const p of expected){
     const scale=doc.policy.categories[p.key].scale;
     if(Math.abs((p.adj-p.line)/scale-p.score)>1e-10)throw Error('Independent scaled gap mismatch');
     if(p.forecast_source==='SELECTED'&&!groups[i].textContent.includes('Selected'))throw Error('Selected source unlabeled');
     if(!(Date.parse(p.selected_at)<Date.parse(p.kickoff_utc)))throw Error('Late ranking');
    }
    result[side]={rows:expected.length,selected:expected.filter(p=>p.forecast_source==='SELECTED').length,
      fallback:expected.filter(p=>p.forecast_source==='R0_FALLBACK').length,dom_membership_order_exact:true,gap_arithmetic:true};
   }
   return {sides:result,default_sort:S.f.sort,ranking_source:doc.website_source_sha,prepared_at:doc.prepared_at};
  });
  const sorts=[];
  for(const category of ['rec','anytime_td']){
   await page.selectOption('#f-cat',category);await page.selectOption('#f-sort','selected_value');
   const checked=await page.evaluate(category=>{
    const visible=[...document.querySelectorAll('[data-player]')].map(n=>S.byId[n.dataset.player]);
    const vals=visible.map(p=>S.weeklyOverlay.rows.get(JSON.stringify([p.game_id,p.id,category]))?.forecast_value??null);
    let missing=false,last=Infinity;
    for(const v of vals){if(v===null){missing=true;continue;}if(missing||v>last)throw Error('Selected sort not descending/missing-last');last=v;}
    return {category,visible:vals.length,nonmissing:vals.filter(v=>v!==null).length,descending:true,missing_last:true};
   },category);sorts.push(checked);
  }
  if(errors.length)throw Error(errors.join(';'));
  scenes.push({width,top,sorts,page_errors:errors});await context.close();
 }}finally{await browser.close();fs.writeFileSync(root+'/evidence/successor-ranking-browser.json',JSON.stringify({observed_at:new Date().toISOString(),scope:'Actual new public release;no injected fixture or production mutation',scenes},null,2)+'\n');}
 console.log(JSON.stringify(scenes));
})().catch(e=>{console.error(e);process.exitCode=1});
