"""Readable aggregate-only projection of closed CMP join versions; no private row reads."""
from pathlib import Path
import csv,gzip,hashlib,io,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/abc-championship/profile-increment-to-release-01/closure-next-02'
OUT=BASE/'b-completion-public-v2'
REFS={1:'1720c675e57263b15856e10f7d201a0b0bdc4361ca2883714cbbaef20376ef2f',2:'1f176b310e93129a70d4dcaccf0a79d2ae9f02d8a48bd9851c83a4c41bd216cc'}
MAX=61440
FILES=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def val(x):return json.dumps(x,sort_keys=True,separators=(',',':'))if isinstance(x,(dict,list))else x
def emit(stem,rows):
    assert rows
    fields=list(rows[0]);chunks=[];chunk=[]
    def render(rr):
        out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows([{k:val(v)for k,v in r.items()}for r in rr]);return out.getvalue().encode()
    for row in rows:
        if chunk and len(render(chunk+[row]))>MAX:chunks.append(chunk);chunk=[]
        chunk.append(row)
    if chunk:chunks.append(chunk)
    for i,c in enumerate(chunks,1):
        raw=render(c);assert len(raw)<=MAX;n=f'{stem}_{i:03d}.csv';(OUT/n).write_bytes(raw);FILES.append(dict(path=n,rows=len(c),bytes=len(raw),sha256=sha(raw)))
def flat(r,source_version):
    n,p=r['numerical'],r['probability'];d=dict(category='pass_cmp',role='QB',source_score_version=source_version,view=r['view'],source_panel=r['source_panel'],week_view=r['week_view'],candidate_id=r['candidate_id'],eligible=r['eligible'],selected=r['COMBINED']['selected'],unavailable=r['unavailable'],abstained=r['abstentions'],games=r['games'],player_games=r['player_games'],retained_threshold_weeks=r['actual_retained_threshold_scored_weeks'],diagnostic_weeks=r['diagnostic_scored_weeks'],five_week_duration_only=r['five_actual_week_duration_only'],source_timing='UNVERIFIED_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE',bookmaker_settlement_unresolved_selected=r['COMBINED']['selected'])
    for side in ['OVER','UNDER','COMBINED']:
        for k in ['wins','losses','decided','rate']:d[side.lower()+'_'+k]=r[side][k]
    for k in ['UNKNOWN_PARTICIPATION','MISSING_ACTUAL','DNP','PENDING','PUSH']:d[k]=r['states'].get(k,0)
    for k in ['scored','MAE','MSE','bias','max_absolute_error','absolute_error_p90']:d['numeric_'+k]=n[k]
    for k in ['events','Brier','three_state_log_loss','infinite_log_loss_cases','neutral_binary_half_Brier','Over_event_AUC']:d['law_'+k]=p[k]
    d.update(source_fallback_flags=r['fallback_states'],no_own_history_queries=r['no_own_history_queries'],unavailability_reasons=r['unavailable_reasons'],eligible_mask_sha256=r['eligible_mask_sha256'],decided_mask_sha256=r['decided_mask_sha256'])
    return d
def pair(r):return dict(r)
def main():
    data={};source=[]
    for v,h in REFS.items():
        p=BASE/f'B_COMPLETION_JOIN_RESULTS_V{v}.json.gz';b=p.read_bytes();assert sha(b)==h;raw=gzip.decompress(b);x=json.loads(raw);assert x['state']=='COMPLETED_OWNER_LOCAL_SAVED_COMPLETION_JOIN';data[v]=x;source.append(dict(version=v,bytes=len(b),sha256=h,decoded_bytes=len(raw),decoded_sha256=sha(raw)))
    assert not OUT.exists();OUT.mkdir()
    s=data[2]['summaries']
    groups=[('ANNUAL_ACTUAL_W1_W5','ANNUAL_NAMED_NJ',['ALL',1,2,3,4,5]),('MIXED_DIAGNOSTIC_W1_W7','ALL',['ALL',1,2,3,4,5,6,7]),('SITE_DIAGNOSTIC_W6_W7','SITE_RECORDED_DK_JURISDICTION_UNKNOWN',['ALL',6,7])]
    for name,panel,weeks in groups:
        rr=[r for r in s if r['view']=='FULL_A_BOARD'and r['source_panel']==panel and r['week_view']in weeks];assert len(rr)==22*len(weeks);emit(name,[flat(r,2)for r in rr])
    alias=[r for r in s if r['view']=='NEWLY_QUALIFIED_ALIAS_ROWS'and r['week_view']=='ALL'];emit('ALIAS_COVERAGE_ONLY',[flat(r,2)for r in alias])
    old=[r for r in data[1]['summaries']if r['view']=='SHARED_ALL_FOUR_B_ARMS'and r['week_view']=='ALL'];emit('PRESERVED_V1_STRICT_TEXT_COMMON',[flat(r,1)for r in old])
    pp=[r for r in data[2]['paired']if r['view']=='FULL_A_BOARD'];assert len(pp)==151*3;emit('MATCHED_WITHIN_METHOD_AND_STRONG_CONTROLS',pp)
    bins=[]
    for r in s:
        if r['view']=='FULL_A_BOARD'and r['week_view']=='ALL'and r['candidate_id'].endswith('::P2'):
            for b in r['probability']['reliability_fixed_bins']:bins.append(dict(source_panel=r['source_panel'],candidate_id=r['candidate_id'],**b))
    emit('FIXED_RELIABILITY_BINS',bins)
    fields=['path','rows','bytes','sha256'];ioo=io.StringIO(newline='');w=csv.DictWriter(ioo,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(FILES);(OUT/'INDEX.csv').write_text(ioo.getvalue())
    manifest=dict(id='A-NEXT02-B-CMP-PUBLIC-AGGREGATE-TABLES-v2',state='PREPARED_FROM_CLOSED_RESULTS_ONLY',source_scores=source,files=FILES,data_files=len(FILES),aggregate_rows=sum(x['rows']for x in FILES),public_player_ids_or_rows=False,scope='All22methods in declared primary/supplementalpanels;151matchedpairsets in3panels;selectedviewdimensions fixed notchosenbyoutcomes. OriginalfullV1/V2source aggregates retained; omitted empty/redundantview dimensions remainthere.',alias_coverage=data[2]['alias_coverage_reconciliation'],new_fits=0,new_grades=0,new_inference=0,private_source_reads=0)
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'README.md').write_text('''# Saved B completion forecasts on A offers — alias-qualified v2

These files contain public aggregate method cells, not player/game/offer rows. All 22 saved point/law/control products are retained, including losing means and medians. P2 and median happen to agree on these half-integer lines; they are not independent learners or extra football observations.

- ANNUAL_ACTUAL_W1_W5: 88 retained completion offers, 51 games. Quote timing is unverified. These are reconstructed actual-line diagnostics, not original issuance or verified settlement.
- MIXED_DIAGNOSTIC_W1_W7: 144 thresholds, 79 games, including 56 separately labelled site-recorded W6–7 thresholds whose offer status is unqualified. This does not establish seven authentic-offer weeks.
- SITE_DIAGNOSTIC_W6_W7 remains separate. The exact A source has no W8 completion rows; this is not proof that every possible source lacks them. No synthetic offer was substituted.
- ALIAS_COVERAGE_ONLY: 11 newly admitted LA/LAR identity matches. Existing qualified 2026 alias normalization preserves LAC and all other team tokens; exact event/player/role/cutoff matching remains required. Predictions, models, lines and outcomes did not change. Recovered coverage is not improved learned-model skill.
- PRESERVED_V1_STRICT_TEXT_COMMON reuses the original 133-case common-mask aggregates, including 81 annual cases. The original full v1 bytes remain unchanged. Do not compare unmatched percentages or pool these overlapping views twice.
- All current arms have zero unavailable forecasts after alias qualification. Outcomes here are known; unknown, DNP, push and pending states remain explicit in the score contract. Bookmaker settlement is unresolved; no price/EV/ROI claim.
- Fixed reliability bins and valid law scores are separate from side accuracy. A point-only A control has no inferred probability. Exact earlier-prevalence outputs on these new lines and B private saved-adjusted/raw controls are unavailable in the selected row transfer; prior B own-board controls remain separate.
- Five retained-line scored weeks satisfy duration only at the disclosed retrospective tier, not primary admission, current-query delivery, probability confidence or Top Picks qualification. No 90% gate was fitted or threshold lowered.

CSV rates are fractions; empty cells mean N/A/null, not zero. Counts and numerical/probability/paired masks are kept separate. File splitting follows a fixed 60 KiB limit, never observed accuracy. Full output hashes and exact scope are in MANIFEST.json and INDEX.csv. This export performs no new scoring, model inference or source acquisition.
''')
    print(json.dumps(dict(state=manifest['state'],files=len(FILES),rows=manifest['aggregate_rows'],bytes=sum(x['bytes']for x in FILES),source_V2_sha256=REFS[2])))
if __name__=='__main__':main()
