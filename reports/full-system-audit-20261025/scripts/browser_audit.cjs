"use strict";
const {chromium} = require('playwright');
const fs = require('fs');
const crypto = require('crypto');
const root = process.env.NFL_AUDIT_ROOT || __dirname;
const base = 'https://nicknicky19.github.io/nicks-expert-nfl-picks/';
const receipt = {observed_at:new Date().toISOString(), tls_verification:true, scenes:[]};
(async()=>{
 const opts={executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']};
 if(process.env.HTTPS_PROXY)opts.proxy={server:process.env.HTTPS_PROXY};
 const browser=await chromium.launch(opts);
 try{
  for(const width of [320,390,1280]){
   const context=await browser.newContext({viewport:{width,height:900}});
   const page=await context.newPage();
   const errors=[], failures=[], responses=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('requestfailed',r=>failures.push({url:r.url().split('?')[0],error:r.failure()?.errorText}));
   page.on('response',r=>{if(r.url().startsWith(base))responses.push({path:r.url().slice(base.length).split('?')[0],status:r.status()})});
   await page.goto(base+'#/props',{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>typeof S!=='undefined'&&S.data&&S.weeklyOverlay,{timeout:30000});
   const contract=await page.evaluate(()=>{
    const counts={};const examples=[];
    for(const r of S.weeklyOverlay.rows.values()){
     if(counts[r.category])continue;
     const p=S.byId[r.player_id];
     const v=selectedPropForecast(p,r.category);
     if(!v)throw Error('Selected row not eligible at current clock: '+r.category);
     const holder=document.createElement('div');holder.innerHTML=catCard(p,p.props.find(x=>x.key===r.category));
     const node=holder.querySelector('[data-weekly-primary]');
     if(!node||!node.textContent.includes(v.text))throw Error('Rendered value differs: '+r.category);
     counts[r.category]={product:r.product,label:v.label,rendered_matches:true};
     examples.push(JSON.stringify([r.game_id,r.player_id,r.category,r.forecast_value,r.selection_sha256]));
    }
    return {categories:counts,trace_keys:examples,rows:S.weeklyOverlay.rows.size,week:S.data.week,season:S.data.season,
       rendered_chips:document.querySelectorAll('[data-weekly-primary]').length,
       width:innerWidth,scroll_width:document.documentElement.scrollWidth,worker_enabled:!!WORKER_URL};
   });
   contract.trace_key_sha256=contract.trace_keys.map(x=>crypto.createHash('sha256').update(x).digest('hex'));delete contract.trace_keys;
   const routes=[];
   for(const route of ['fantasy','compare','league','trade','mine','teams','record','about','props']){
    await page.locator('nav.tabs [data-tab="'+route+'"]').click();
    await page.waitForTimeout(route==='teams'||route==='record'?1000:150);
    routes.push(await page.evaluate(()=>({hash:location.hash,main_has_content:document.querySelector('#main').textContent.trim().length>0,
       scroll_width:document.documentElement.scrollWidth,width:innerWidth})));
   }
   await page.reload({waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>typeof S!=='undefined'&&S.weeklyOverlay,{timeout:30000});
   const refresh=await page.evaluate(()=>({hash:location.hash,rows:S.weeklyOverlay.rows.size,main_has_content:!!document.querySelector('#main').textContent.trim()}));
   receipt.scenes.push({width,contract,routes,refresh,page_errors:errors,request_failures:failures,site_responses:responses});
   await context.close();
  }
 }finally{await browser.close();fs.writeFileSync(root+'/evidence/live-browser.json',JSON.stringify(receipt,null,2)+'\n')}
 console.log(JSON.stringify(receipt,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
