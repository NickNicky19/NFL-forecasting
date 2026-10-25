'use strict';
const {chromium}=require('playwright');
const fs=require('fs');
const root=process.env.NFL_AUDIT_ROOT || __dirname,base='https://nicknicky19.github.io/nicks-expert-nfl-picks/';
(async()=>{
 const opts={executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']};
 if(process.env.HTTPS_PROXY)opts.proxy={server:process.env.HTTPS_PROXY};
 const browser=await chromium.launch(opts);const results=[];
 try{
  for(const mode of ['unavailable-overlay','hash-mismatch','missing-board','empty-players']){
   const context=await browser.newContext({viewport:{width:390,height:844}});
   const page=await context.newPage();const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/data/weekly-adaptive-overlay.json',r=>mode==='unavailable-overlay'?r.abort():r.continue());
   if(mode==='hash-mismatch')await page.route('**/data/weekly-adaptive/*.json',r=>r.fulfill({status:200,contentType:'application/json',body:'{}'}));
   if(mode==='missing-board')await page.route('**/data/week.json*',r=>r.fulfill({status:503,body:'Unavailable'}));
   if(mode==='empty-players')await page.route('**/data/week.json*',r=>{
    const board=JSON.parse(fs.readFileSync(root+'/website-audit/output/data/week.json','utf8'));
    board.players=[];board.picks={over:[],under:[]};
    return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(board)});
   });
   await page.goto(base+'#/props',{waitUntil:'domcontentloaded',timeout:60000});
   if(mode==='missing-board')await page.waitForFunction(()=>document.querySelector('#main').textContent.includes("Couldn't load this week's data"));
   else await page.waitForFunction(()=>typeof S!=='undefined'&&S.weeklyOverlayReady&&S.data);
   await page.waitForTimeout(4500);
   const state=await page.evaluate(()=>({has_board:!!S.data,selected_rows:S.weeklyOverlay?.rows.size||0,
    cards:document.querySelectorAll('[data-player]').length,primary_nodes:document.querySelectorAll('[data-weekly-primary]').length,
    main_has_content:!!document.querySelector('#main').textContent.trim(),
    load_error:document.querySelector('#main').textContent.includes("Couldn't load this week's data"),
    empty_message:/no players|nothing|no match/i.test(document.querySelector('#main').textContent)}));
   if(state.selected_rows!==0||state.primary_nodes!==0||errors.length)throw Error(mode+': invalid selected fallback');
   if(mode==='missing-board'&&!state.load_error)throw Error('Missing board did not show error');
   if(['unavailable-overlay','hash-mismatch'].includes(mode)&&state.cards===0)throw Error('R0 board unusable');
   results.push({mode,...state,page_errors:errors});await context.close();
  }
 }finally{await browser.close();fs.writeFileSync(root+'/evidence/browser-failures.json',JSON.stringify({observed_at:new Date().toISOString(),scope:'Controlled response faults in actual deployed app; no server or production mutation',results},null,2)+'\n')}
 console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1});
