'use strict';
// Reuse the actual existing test fixture/context, then add the wrong-side control.
// No source/test file is modified. Only fictional fixture code executes.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const root=path.resolve(process.argv[2]),filename=path.join(root,'tests/test-selected-rankings.cjs');
const source=fs.readFileSync(filename,'utf8'),marker='(async () => {';
if(source.split(marker).length!==2)throw Error('Exact retained fixture boundary changed');
const prefix=source.slice(0,source.indexOf(marker));
const extra=`
(async()=>{
  await context.validateSelectedRankings(fixture.ranking,fixture.pointer,S.data,S.weeklyOverlay);
  const bad=clone(fixture.ranking);
  bad.picks.under.push(bad.picks.over.shift());
  bad.picks.under.sort(context.compareSelectedRankingItems);
  await assert.rejects(()=>context.validateSelectedRankings(bad,fixture.pointer,S.data,S.weeklyOverlay),/Ranking source\\/clock/);
  console.log(JSON.stringify({state:'PASS',checks:2,HTTP:0,scope:'Actual current JS validator, ordinary artifact control and wrong-side rejection'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
`;
const review=new Module(filename,module);review.filename=filename;
review.paths=Module._nodeModulePaths(path.dirname(filename));review._compile(prefix+extra,filename);
