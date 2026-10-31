"""Metadata-only plan builder: reuse saved laws across admitted run namespaces.

Lexical projection skips every loss/result subtree. Opaque member hashing and
Parquet footer inspection never deserialize probability or outcome rows. Root
owns private config persistence, source admission, capacity and eventual GO.
"""
from pathlib import Path
import gzip,hashlib,importlib.util,io,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
PROJECTOR_SHA='0d29fd53fb80755248d22177a984df26111044fa1ab3a183f3e8d45c534d1f2d'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def build(request):
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 import pyarrow.parquet as pq
 pr=request['projector'];assert pr['sha256']==PROJECTOR_SHA;read_exact(pr)
 s=importlib.util.spec_from_file_location('conditional_plan_metadata_projector',pr['path']);projector=importlib.util.module_from_spec(s);s.loader.exec_module(projector)
 def projection(r,fields):
  b=read_exact(r);b=gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b
  return projector.project(b,set(fields),maximum_bytes=16*1024**2)
 cells={};audits=[];duplicates=[];suppressed=[];expected=set(request['expected_law_cell_ids'])
 for source in request['law_admissions']:
  doc,audit=projection(source['source_report'],[('version',),('state',),('cells','*','cell_id'),('cells','*','state'),('cells','*','artifact','bytes'),('cells','*','artifact','sha256')]);audits.append({'source_report_sha256':source['source_report']['sha256'],**audit})
  bindings,ba=projection(source['evaluation_bindings'],[('labels_sha256',),('offers_sha256',)])
  assert bindings['labels_sha256']==request['labels_sha256'] and bindings['offers_sha256']==request['prepared_offers_sha256']
  root=Path(source['run_root']);assert root.is_absolute() and root.resolve()==root
  for row in doc['cells']:
   cid=row['cell_id']
   if cid not in expected:continue
   if row['state']!='SCORED_FROZEN_LAW':suppressed.append({'cell_id':cid,'source_report_sha256':source['source_report']['sha256'],'state':row['state']});continue
   assert '/' not in cid and cid not in ['.','..'];p=root/cid/'SCORE_PACKAGE.zip';r={'path':str(p),**{k:row['artifact'][k] for k in ['bytes','sha256']}};body=read_exact(r)
   with zipfile.ZipFile(io.BytesIO(body)) as z:
    assert len(z.namelist())==len(set(z.namelist()))<=8
    header,ha=projector.project(z.read('MANIFEST.json'),{('spec','cell_id'),('spec','target'),('spec','methods','*'),('law_helper_sha256',)},maximum_bytes=1024**2)
    assert header['spec']['cell_id']==cid and header['law_helper_sha256']==request['source_pins']['loss']['sha256'];target=header['spec']['target'];footer=None
    if target in ['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd']:
     raw=z.read('OFFER_PROBABILITY_SCORECARD.parquet');pf=pq.ParquetFile(io.BytesIO(raw));footer={'rows':pf.metadata.num_rows,'columns':len(pf.schema_arrow.names),'member_sha256':sha(raw),'semantic_rows_decoded':0}
   candidate={'cell_id':cid,'target':target,'package':r,'source_report':source['source_report'],'evaluation_bindings':source['evaluation_bindings']}
   if cid in cells:
    assert cells[cid]['package']['sha256']==r['sha256'],'conflicting same-ID saved law packages: explicit new candidate/admission required'
    duplicates.append({'cell_id':cid,'same_bytes_reused_once':True,'source_report_sha256':source['source_report']['sha256']});continue
   cells[cid]=candidate;audits.append({'cell_id':cid,'package_sha256':r['sha256'],'header_projection':ha,'footer':footer})
 missing=sorted(expected-set(cells));assert not missing,('missing declared source law cells',missing)
 needrows=sum(a['footer']['rows'] for a in audits if isinstance(a,dict) and a.get('footer'))
 assert needrows<=request['resources']['maximum_source_offer_records']
 config={'version':'matched12-exploratory-conditional-market-score-v1','run_id':request['run_id'],'allocation_sha256':request['allocation_sha256'],'price_packet':request['price_packet'],'labels_sha256':request['labels_sha256'],'prepared_offers_sha256':request['prepared_offers_sha256'],'law_inputs':[cells[k] for k in sorted(cells)],'expected_law_cell_ids':sorted(expected),'source_failures':request.get('source_failures',[]),'source_pins':request['source_pins'],'uncertainty':{'replicates':1000,'seed':20261030,'minimum_clusters':2},'resources':request['resources']}
 manifest={'state':'METADATA_PLAN_ONLY_NOT_SOURCE_SCORING_OR_RESTORATION_ADMISSION','configuration_sha256':sha(enc(config)),'source_law_cells':len(cells),'source_namespaces':len(request['law_admissions']),'projected_offer_records':needrows,'missing':missing,'duplicate_samebyte_sources_reused_once':duplicates,'suppressed_source_states':suppressed,'projection_audits':audits,'actual_probability_outcome_rows_decoded':0,'models_fits_HTTP':0,'root_remaining_actions':'Validate complete private capacity, source ownership and exact configuration; persist config; issue exact worker/config GO; run scoring.'}
 return config,manifest
