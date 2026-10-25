"""Finite metadata/hash/footer assembly, with actual numerical decoders denied."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import signal
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('/tmp/anytime-calibration-v1-EXECUTION-OUTER.json')
PARENT_SHA='12b6de9ddddf5c83b53f3fc9e99b761d6a8a248860d9620b9d1f6d368e727edd'


def ref(path):
    path=Path(path)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest)


def build(destination):
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(30,30));signal.alarm(45)
    assert ref(PARENT)['sha256']==PARENT_SHA
    parent=json.loads(PARENT.read_text())
    import pyarrow.parquet as pq
    def denied(*a,**k):raise RuntimeError('numerical row decoding forbidden during preparation')
    pq.read_table=pq.read_pandas=denied
    for name in ['read','read_row_group','read_row_groups','iter_batches']:setattr(pq.ParquetFile,name,denied)
    schemas={}
    for year,item in parent['contexts'].items():
        file=pq.ParquetFile(item['path']);names=file.schema_arrow.names
        assert {'season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc','outcome_available_utc'}<=set(names)
        assert ref(item['path'])==item
        schemas['context/'+year]=dict(rows=file.metadata.num_rows,columns=names)
    for base,packet in parent['bases'].items():
        for year,items in packet['years'].items():
            for kind in ['forecast','labels']:
                item=items[kind];assert ref(item['path'])==item
                file=pq.ParquetFile(item['path']);names=file.schema_arrow.names
                required={packet['probability_column'],'fallback'} if kind=='forecast' else {'actual','participation_state'}
                assert required|{'season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc'}<=set(names)
                schemas[base+'/'+year+'/'+kind]=dict(rows=file.metadata.num_rows,columns=names)
    names=['nfl_lab/anytime_td_blend.py','tools/run_anytime_td_blend_v1.py','tools/launch_anytime_td_blend_v1.py',
           'tools/prepare_anytime_td_blend_v1.py','tools/threshold_cdf_wave_supervisor.py']
    code={name:ref(ROOT/name) for name in names}
    assert code['tools/threshold_cdf_wave_supervisor.py']['sha256']=='1ef8e8a4109ebc2c098e6f814d72e7aeb17da66cba31d0dfea809d6ac7d751a6'
    output='/workspace/website-methods-research/resumed/anytime-td-blend-v1-20261025'
    assert not Path(output).exists()
    registration=ref(ROOT/'config/anytime-td-blend-v1.json')
    value=dict(state='PREPARED_UNSEALED_NO_GO',registration=registration,code=code,
        parent_execution=ref(PARENT),parent_GO=ref(parent['root_go_path']),shared_runner=parent['worker']['script'],
        blend_module=code['nfl_lab/anytime_td_blend.py'],thread_helper=parent['thread_helper'],libc=parent['libc'],
        contexts=parent['contexts'],bases=parent['bases'],environment=parent['environment'],
        worker=dict(cwd=str(ROOT),script=code['tools/run_anytime_td_blend_v1.py'],interpreter=parent['worker']['interpreter']),
        outer_supervisor=dict(launcher=code['tools/launch_anytime_td_blend_v1.py'],core=code['tools/threshold_cdf_wave_supervisor.py'],
            receipt='/tmp/anytime-td-blend-v1-SUPERVISOR.json',receipt_reserve_bytes=65536,worker_terminal_reserve_bytes=65536,
            parent_import_contract='Fresh isolated stdlib monitor; numerical/Arrow imports only in worker'),
        output=output,required_root_GO='/tmp/anytime-td-blend-v1-GO.json',
        preexec_requirements=dict(review_state='PASS_EXACT_ANYTIME_TD_BLEND_PREEXEC',root_GO_state='ROOT_GO_SINGLE_ANYTIME_TD_BLEND',
            review_binds='exact manifest SHA256',GO_binds='exact manifest/registration/review plus root seal, one invocation, zero retries'),
        preparation=dict(NFL_numeric_reads=0,model_CAS_HTTP=0,footer_schemas=schemas,
            CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start))
    body=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode();assert len(body)<16777216
    with Path(destination).open('xb') as stream:stream.write(body)
    signal.alarm(0)
    return dict(manifest=ref(destination),state=value['state'],preparation=value['preparation'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args()
    value=build(args.destination);value['preparation'].pop('footer_schemas')
    print(json.dumps(value,indent=2))
