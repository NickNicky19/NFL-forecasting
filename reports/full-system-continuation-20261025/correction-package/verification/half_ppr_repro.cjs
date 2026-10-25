/* Fictional scoring-label checks using actual saved function bodies.
 * No DOM/browser, selected consumer, package install, or network operations.
 * Exit zero asserts the missing-half fallback defect is independently present.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const audit = __dirname;
const args = process.argv.slice(2);
const rootArg = args.indexOf('--root');
const patched = args.includes('--expect-patches');
const roots = rootArg >= 0 ? [['DISPOSABLE_SOURCE_COPY', args[rootArg + 1]]] :
  ['website-audit', 'website-phase2'].map(name => [name, path.join(audit,name)]);
const results = {};
for (const [name,root] of roots) {
  const source = fs.readFileSync(path.join(root, 'output/app.js'), 'utf8');
  const functions = ['projPts', 'avgPts', 'scoringName', 'pv', ...(patched ? ['propChip','catCard'] : [])].map(name => {
    const found = source.match(new RegExp('^function ' + name + '\\([^]*?^}', 'm'));
    assert(found, name + ' source function missing');
    return found[0];
  }).join('\n');
  const context = vm.createContext({S: {sc: {mode: 'sleeper', half: true}},
                                  isDefault: () => true, currentLeague: () => null});
  vm.runInContext(functions, context);
  const observed = vm.runInContext(`({
    label: scoringName(),
    projection: projPts({pos:'WR',proj_ppr:20,proj_half:null}),
    average: avgPts({pos:'WR',avg_ppr:12,avg_half:null}),
    prop: pv({pos:'WR'}, {key:'fpts',proj:20,adj:21,line:21.5,values:[],adj_h:null})
  })`, context);
  assert.equal(observed.label, 'Sleeper Half PPR');
  assert.equal(observed.projection, patched ? null : 20);
  assert.equal(observed.average, patched ? null : 12);
  assert.equal(observed.prop.line, patched ? null : 21.5);
  // Known half-PPR zero must remain zero; it is not a missing value.
  assert.equal(vm.runInContext("projPts({pos:'WR',proj_ppr:20,proj_half:0})", context), 0);
  if (patched) {
    assert.equal(observed.prop.adj, null);
    assert.equal(observed.prop.lean, null);
    for (const render of ['propChip','catCard']) {
      const html=vm.runInContext(`${render}({pos:'WR'}, {key:'fpts',proj:20,adj:21,line:21.5,values:[],adj_h:null})`,context);
      assert.match(html,/Half PPR.*unavailable/);
      assert(!html.includes('21.5') && !html.includes('null'));
    }
    const known=vm.runInContext(`pv({}, {key:'fpts',proj:20,adj:21,line:21.5,lean:'over',
      proj_h:0,adj_h:0,line_h:.5,over_h:999,n:999,values:[{v:20,h:0},{v:21,h:null},{v:30,h:2}]})`,context);
    assert.equal(known.scoring_missing,false);
    assert.equal(known.adj,0);assert.equal(known.proj,0);assert.equal(known.line,.5);
    assert.equal(known.n,2);assert.equal(known.over,1);
    assert.deepEqual(Array.from(known.values,x=>x.v),[0,2]);
    assert.equal(vm.runInContext("projPts({pos:'K',proj_ppr:7,proj_half:null})", context),7);
    vm.runInContext('S.sc.half=false',context);
    assert.equal(vm.runInContext("projPts({pos:'WR',proj_ppr:20,proj_half:null})",context),20);
    assert.equal(vm.runInContext("avgPts({pos:'WR',avg_ppr:12,avg_half:null})",context),12);
  }
  results[name] = observed;
}
process.stdout.write(JSON.stringify({evidence:patched?'FICTIONAL_HALF_PPR_PATCH_CHECK':'FICTIONAL_MISSING_HALF_LABEL_COUNTEREXAMPLE',results}, null, 2) + '\n');
