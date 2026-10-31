"""Root execution binding; no new fit or acquisition; private configuration stays private."""
import gzip,hashlib,json,os,resource,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_lab
from tools import category_topfive_matched12_storage_v1 as storage
from tools import category_topfive_matched12_exploratory_market_score_v1 as worker

def main():
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    prep=storage.prepare(ROOT)
    forward=Path(prep['allocation']['store_policy']['storage']['forward_root'])
    original=forward/'research/matched12-exploratory-conditional-configuration-v1-20261031/CONFIG.json.gz'
    raw=original.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='2a587874cd636a24a2b45e6125ac78e5a7456f2c06eca1119db8a96dc9cda692'
    config=json.loads(gzip.decompress(raw))
    assert worker.sha(worker.enc(config))=='60dcc521d1442b7542f01958159f34143801645d64b115b931db4b516e1d2c82'
    config['resources']['CPU_seconds']=236
    config['run_id']='matched12-exploratory-conditional-score-v1-1-20261031'
    digest=worker.sha(worker.enc(config))
    go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root',
        'worker_sha256':'9310d01228249f42d47d96689474f5d7c859fa8720ee02aeacc5744b5721189b',
        'configuration_sha256':digest}
    report_root=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/exploratory-market'
    reg={'version':'conditional-execution-v1.1','state':'REGISTERED_BEFORE_SCORING',
        'preparation_state':'RESOURCE_FAILED_POSTRETENTION','preparation_CPU_seconds':63.0469,
        'original_unexecuted_score_CPU_limit':240,'score_CPU_limit':236,
        'shared_CPU_limit':300,'remaining_CPU_margin':.9531,
        'retained_configuration_admission':'Authenticated retained content; preparation overrun unchanged',
        'old_configuration_sha256':'60dcc521d1442b7542f01958159f34143801645d64b115b931db4b516e1d2c82',
        'configuration_sha256':digest,'source_sha256':go['worker_sha256'],
        'run_id':config['run_id'],'fits_HTTP_production_writes':0,
        'evidence':'TIMING_UNVERIFIED_EXPLORATORY_NOT_AUTHENTIC_PREGAME_OR_EV'}
    target=report_root/'EXECUTION_REGISTRATION_V1_1.json'
    assert not target.exists()
    target.write_bytes(worker.enc(reg))
    receipt,report=worker.execute(config,go)
    (report_root/'ACTUAL_EXECUTION_V1_1.json').write_bytes(worker.enc(receipt))
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':main()
