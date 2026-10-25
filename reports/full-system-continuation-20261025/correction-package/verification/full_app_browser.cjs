'use strict';
// Actual complete HTML/CSS/app on a fully intercepted fictional origin.
// No real board, outcome, provider response, account, or paid service is loaded.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(process.argv[2]);
const evidence = path.resolve(process.argv[3]);
const origin = 'http://correction-review.invalid';
const category = (label, scale, lean, min_pick=null) => ({label,scale,lean,min_pick});
const categories = {rec:category('Receptions',1.2,.3,1.5), rec_yd:category('Receiving Yards',12,4,15.5),
  fpts:category('Fantasy Points (PPR)',4,1), anytime_td:category('Anytime TD',1,0)};
const values = [{s:2031,w:1,v:20,h:0},{s:2031,w:2,v:21,h:null},{s:2031,w:3,v:30,h:2}];
function player(id, name, half) {
  return {id,name,pos:'WR',team:'AAA',opp:'BBB',game_id:'fictional-game',espn_id:null,late:false,
    injury:null,props:[
      {key:'rec',proj:6,adj:6,line:4.5,lean:'over',line_from:'dk',values:[{s:2031,w:1,v:6}],n:1,over:1,mf:1,source:'model'},
      {key:'fpts',proj:20,adj:21,line:21.5,lean:'under',line_from:'ours',
        proj_h:half,adj_h:half,line_h:half===null?null:.5,values:structuredClone(values),n:3,over:1,mf:1,source:'model'}],
    proj_ppr:20,avg_ppr:12,proj_half:half,avg_half:half,
    log:[],games_this_season:3,matchup:{label:'neutral'}};
}
const board = {season:2031,week:7,generated_at:'2026-10-25T01:00:00Z',categories,
  scoring:{rec:1,rec_yd:.1,rush_yd:.1,pass_yd:.04,pass_td:4,rush_td:6,rec_td:6},
  games:[{id:'fictional-game',home:'AAA',away:'BBB',kickoff:'2031-10-25T17:00:00Z',state:'pre',detail:'Scheduled',home_score:null,away_score:null,odds:null,ours:null}],
  players:[player('fictional-missing','FICTIONAL Missing Half',null),player('fictional-zero','FICTIONAL Zero Half',0),player('fictional-known','FICTIONAL Known Half',10)],
  picks:{over:[],under:[]}};
let checks=0;
const eq=(a,b,why)=>{assert.deepEqual(a,b,why);checks++;};
const scenes=[];
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.NFL_CHROMIUM_PATH||'/usr/bin/chromium',headless:true,
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-sync']});
  try {
    for(const width of [320,390,1280]) {
      const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
      const startChecks=checks,errors=[],blocked=[],served=[];
      let observedRequests=0,interceptedRequests=0;
      context.on('request',()=>observedRequests++);
      await context.route('**/*',async route=>{
        interceptedRequests++;
        const request=route.request(),url=new URL(request.url());
        if(url.origin!==origin){blocked.push({host:url.hostname,type:request.resourceType()});return route.abort('blockedbyclient');}
        const name=decodeURIComponent(url.pathname).slice(1)||'index.html';
        served.push(name);
        if(name==='data/week.json')return route.fulfill({contentType:'application/json',body:JSON.stringify(board)});
        if(name==='data/meta.json')return route.fulfill({contentType:'application/json',body:JSON.stringify({generated_at:board.generated_at})});
        if(name==='data/future.json')return route.fulfill({contentType:'application/json',body:'{"players":{},"byes":{}}'});
        const staticFiles=new Set(['index.html','style.css','app.js','reliability-ui.js','weekly-adaptive-overlay.js']);
        if(!staticFiles.has(name))return route.fulfill({status:404,body:'Fictional optional artifact unavailable'});
        const file=path.join(root,'output',name),type=name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html';
        return route.fulfill({contentType:type,body:fs.readFileSync(file)});
      });
      const page=await context.newPage();
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(origin+'/#/props');
      await page.waitForFunction(()=>typeof S!=='undefined'&&S.data&&!ticking&&document.querySelectorAll('.player').length===3);
      eq(await page.locator('.player').count(),3,'actual full app starts with fictional players');
      eq(await page.evaluate(()=>projPts(S.byId['fictional-missing'])),20,'full PPR control');
      await page.locator('#sc-btn').click();
      await page.locator('[data-sc="sleeper|half"]').click();
      eq(await page.locator('#sc-btn').innerText(),'Sleeper Half PPR ▾','actual scoring button changes mode');
      eq(await page.evaluate(()=>projPts(S.byId['fictional-missing'])),null,'missing half headline unknown');
      eq(await page.evaluate(()=>avgPts(S.byId['fictional-missing'])),null,'missing half average unknown');
      eq(await page.locator('[data-player="fictional-missing"] .pts .v').allTextContents(),['-','-'],'full card headlines use existing unavailable glyph');
      eq((await page.locator('[data-player="fictional-missing"] .props-row').innerText()).includes('Half PPR unavailable'),true,'collapsed missing half chip');
      await page.locator('[data-toggle="fictional-missing"]').click();
      eq((await page.locator('[data-player="fictional-missing"] .pbody').innerText()).includes('Half PPR projection and line unavailable.'),true,'expanded missing half card');
      eq(await page.evaluate(()=>({p:projPts(S.byId['fictional-zero']),a:avgPts(S.byId['fictional-zero'])})),{p:0,a:0},'known half zero remains zero');
      eq((await page.locator('[data-player="fictional-zero"] .props-row').innerText()).includes('unavailable'),false,'known zero chip is available');
      eq(await page.evaluate(()=>{const p=S.byId['fictional-zero'],x=pv(p,p.props[1]);return {v:x.values.map(x=>x.v),n:x.n,over:x.over};}),{v:[0,2],n:2,over:1},'half history uses known values only');
      eq(await page.evaluate(()=>projPts(S.byId['fictional-known'])),10,'known half control');
      eq(await page.evaluate(()=>projPts({pos:'K',proj_ppr:7,proj_half:null})),7,'K ESPN standard retained');
      eq(await page.evaluate(()=>projPts({pos:'DEF',proj_ppr:8,proj_half:null})),8,'DEF ESPN standard retained');
      await page.locator('#sc-btn').click();
      await page.locator('[data-sc="sleeper|ppr"]').click();
      eq(await page.evaluate(()=>projPts(S.byId['fictional-missing'])),20,'return to PPR restores headline');
      eq((await page.locator('[data-player="fictional-missing"] .props-row').innerText()).includes('Half PPR unavailable'),false,'return to PPR restores prop');
      // The caption release and reversible live grading must survive the patch.
      await page.evaluate(()=>{
        const p=S.byId['fictional-missing'];S.games[p.game_id].state='in';
        S.live[p.id]={gp:1,rec:6,rec_yd:10};
        S.mine=[{pid:p.id,key:'rec',dir:'over',line:4.5,season:S.data.season,week:S.data.week,at:1}];
      });
      await page.locator('[data-tab="mine"]').click();
      const mine=await page.locator('#main').innerText();
      eq(mine.includes('Live prop values remain provisional, including overs already above the line'),true,'new caption rendered in actual My Picks route');
      eq(mine.includes('Overs show cleared as soon as they pass the line'),false,'obsolete finality caption absent');
      eq(await page.evaluate(()=>propStatus(S.byId['fictional-missing'],'rec',4.5,'over').res),'live','over above line remains provisional');
      await page.evaluate(()=>{S.live['fictional-missing'].rec=4;});
      eq(await page.evaluate(()=>propStatus(S.byId['fictional-missing'],'rec',4.5,'over').res),'live','downward correction stays provisional');
      await page.locator('[data-tab="props"]').click();
      eq(await page.locator('#f-sort option[value="selected_edge"]').count(),1,'selected gap sorting option survives');
      eq(await page.locator('#f-sort option[value="selected_value"]').count(),1,'selected category sorting option survives');
      eq(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'full app has no horizontal overflow');
      eq(errors,[],'no page exceptions with blocked providers');
      eq(observedRequests,interceptedRequests,'every browser request intercepted');
      scenes.push({width,checks:checks-startChecks,blocked_external_requests:blocked.length,fulfilled_fictional_requests:served.length,page_errors:errors,
        observed_requests:observedRequests,intercepted_requests:interceptedRequests});
      fs.mkdirSync(evidence,{recursive:true});
      await page.screenshot({path:path.join(evidence,'full-app-'+width+'.png'),fullPage:false});
      await context.close();
    }
    console.log(JSON.stringify({state:'PASS',checks,widths:[320,390,1280],scenes,network:'ALL_ROUTES_INTERCEPTED_NO_CONTINUE',actual_network_requests:0,
      source_scope:'Entire current HTML/CSS/JS, fictional input only',provider_requests:0}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
