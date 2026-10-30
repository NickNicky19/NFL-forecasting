"""Finite exact-served consumer value readback, without outcomes or producer writes."""
from pathlib import Path
import datetime
import hashlib
import json
import resource
import subprocess
import time
import urllib.request

NODE = r'''
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const index=new Map(input.rows.map(r=>[JSON.stringify([r.game_id,r.player_id,r.category]),r]));
const context=vm.createContext({S:{weeklyOverlay:{rows:index}},Map,Set,Date,JSON,Number,console:{log(){}}});
vm.runInContext(input.overlay,context,{timeout:1000});
vm.runInContext(input.consumer,context,{timeout:1000});
const groups=new Map(),before=JSON.stringify(input.rows);
for(const row of input.rows){
 const result=context.selectedPropForecast({id:row.player_id,game_id:row.game_id},row.category,input.now);
 const g=groups.get(row.category)||{category:row.category,published_rows:0,consumer_values_equal_saved:0,not_displayable:0,labels:{},sample_public_value:null};
 g.published_rows++;
 if(result===null)g.not_displayable++;
 else{
  if(result.value!==row.forecast_value)throw Error('Consumer changed a published forecast');
  g.consumer_values_equal_saved++;g.labels[result.label]=(g.labels[result.label]||0)+1;
  if(g.sample_public_value===null)g.sample_public_value={row_sha256:crypto.createHash('sha256').update(JSON.stringify(row)).digest('hex'),value:result.value,formatted_text:result.text,label:result.label,product:row.product,functional:row.prediction_functional};
 }
 groups.set(row.category,g);
}
if(JSON.stringify(input.rows)!==before)throw Error('Readback mutated source forecasts');
process.stdout.write(JSON.stringify({categories:[...groups.values()].sort((a,b)=>a.category.localeCompare(b.category)),rows:input.rows.length,source_values_unchanged:true}));
'''


def main():
    folder=Path(__file__).resolve().parents[1]/'reports/category-topfive-mae-release-priority-20261030'
    protocol=json.loads((folder/'SERVED_CONSUMER_READBACK_PROTOCOL_V1.json').read_bytes())
    out=folder/'SERVED_CONSUMER_READBACK_V1.json'
    assert not out.exists()
    started=time.monotonic();cpu=time.process_time();attempts=0
    base='https://nicknicky19.github.io/nicks-expert-nfl-picks/'
    def get(path,cap):
        nonlocal attempts
        attempts+=1;assert attempts<=3
        with urllib.request.urlopen(base+path,timeout=5) as response:
            body=response.read(cap+1)
        assert 0<len(body)<=cap
        return body
    try:
        pin=protocol['pins'];body=get('data/weekly-adaptive/'+pin['payload_sha256']+'.json',2097152)
        assert len(body)==pin['payload_bytes'] and hashlib.sha256(body).hexdigest()==pin['payload_sha256']
        app=get('app.js',524288);overlay=get('weekly-adaptive-overlay.js',16384)
        def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        assert blob(app)==pin['app_git_blob'] and blob(overlay)==pin['overlay_git_blob']
        text=app.decode();start=text.index('function selectedPropForecast(');end=text.index('\n}\n',start)+3
        consumer=text[start:end]
        assert len(consumer)<3000 and consumer.count('function selectedPropForecast(')==1
        now=datetime.datetime.now(datetime.timezone.utc)
        argument=json.dumps({'rows':json.loads(body)['rows'],'overlay':overlay.decode(),'consumer':consumer,'now':now.timestamp()*1000})
        result=subprocess.run(['node','--max-old-space-size=128','-e',NODE],input=argument,text=True,capture_output=True,timeout=10,check=True)
        values=json.loads(result.stdout)
        output={'version':protocol['version'],'state':'EXACT_SERVED_CONSUMER_FUNCTION_VALUES_VERIFIED',
            'at_UTC':now.isoformat(),'website_main':'1ec93e068a91abd51c990937d1019e4a831694b4',
            'source_pins':pin,**values,'HTTP_GETs':attempts,'CPU_seconds_python':time.process_time()-cpu,
            'wall_seconds':time.monotonic()-started,'new_fits_models_forecasts_capture_deployment':0,
            'consumer_source_bytes':len(consumer.encode()),
            'scope':'Actual served payload and JavaScript bytes authenticated; actual consumer functions executed. Browser DOM not visually observed. All original issue times remain unchanged.'}
        encoded=(json.dumps(output,indent=2,allow_nan=False)+'\n').encode()
        assert len(encoded)<=65536 and output['wall_seconds']<30
        out.write_bytes(encoded)
        print(json.dumps({'state':output['state'],'rows':values['rows'],'category_counts':[(r['category'],r['consumer_values_equal_saved'],r['not_displayable']) for r in values['categories']],'HTTP_GETs':attempts,'wall_seconds':output['wall_seconds']}))
    except BaseException as exc:
        failure={'version':protocol['version'],'state':'FAILED_RETAINED','type':type(exc).__name__,'error':str(exc),'HTTP_attempts':attempts,'wall_seconds':time.monotonic()-started,'new_fits_models_forecasts_capture_deployment':0}
        (folder/'SERVED_CONSUMER_READBACK_FAILURE_V1.json').write_text(json.dumps(failure,indent=2)+'\n')
        raise


if __name__=='__main__':
    main()
