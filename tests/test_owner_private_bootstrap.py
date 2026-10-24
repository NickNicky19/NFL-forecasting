"""Fifteen fictional cases: no credential discovery, real HTTP or private bytes."""
import base64
from contextlib import contextmanager,redirect_stdout
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import urlsplit,parse_qs

from nfl_lab import private_draft_store as s,owner_bootstrap_bundle as b,owner_private_bootstrap as o
from tools import owner_private_bootstrap_v1 as cli

SOURCE='a'*40
CURRENT='b'*40
RUN='40000000001'
RESTORE_RUN='40000000002'
POLICY='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'


class Response:
    def __init__(self,body,status=200,headers=None):
        self.body=body if isinstance(body,bytes) else s.canonical(body);self.status=status
        self.headers={'X-RateLimit-Remaining':'999','Content-Length':str(len(self.body)),**(headers or {})}
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return self.body[:n]


def qualification(binding):
    now=datetime.now(timezone.utc)-timedelta(minutes=30);proofs=[]
    for index,(phase,permission,name) in enumerate(zip(('write_pin','read_boundary','qualified'),('write','read','write'),('pin','boundary','qualify'))):
        start=now+timedelta(minutes=2*index);end=start+timedelta(seconds=30)
        proof=dict(schema_version='weekly-private-proof-v2.1',phase=phase,operation=s.PHASE_OPERATION[phase],repository=s.REPO,
            run_id=RUN,run_attempt=1,started_at_utc=start.isoformat(),created_at_utc=end.isoformat(),source_sha=SOURCE,
            binding_sha256=s.sha(s.canonical(binding)),config_sha256=s.config_sha(),process_identity=s.sha(name.encode()),
            job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=SOURCE,
                job_id=name,permission=permission,event_name='workflow_dispatch',api_job_id=101+index,run_authenticated=True),
            HTTP_calls=17 if phase=='read_boundary' else 7,transfer_bytes=1000)
        if phase=='write_pin':proof.update(exact_canary_readback=True,draft_before_after=True)
        if phase=='read_boundary':
            routes=[]
            for i in range(10):
                anonymous=i>=5 or s.ROUTES[i%5]=='browser'
                routes.append(dict(sequence='anonymous' if i>=5 else 'read_only',principal='anonymous' if anonymous else 'contents_read',route=s.ROUTES[i%5],
                    status=404 if anonymous else 403,resource_permission_message_exact_match=not anonymous,rate_header_present=True,
                    rate_remaining_nonzero=True,retry_after_present=False,request_failed=False))
            proof.update(before_sha256=s.sha(s.canonical(proofs[0])),all10_denied=True,controls_passed=True,routes=routes)
        if phase=='qualified':proof.update(engineering_boundary_v2=True,strict_v1_unchanged='INCONCLUSIVE',restricted_upload_authorized=False,
            before_sha256=s.sha(s.canonical(proofs[0])),read_sha256=s.sha(s.canonical(proofs[1])),before_process_identity=proofs[0]['process_identity'],
            read_process_identity=proofs[1]['process_identity'],before_completed_at_utc=proofs[0]['created_at_utc'],read_completed_at_utc=proofs[1]['created_at_utc'],
            before_proof=proofs[0],read_proof=proofs[1])
        proofs.append(proof)
    return proofs[-1]


class Server:
    def __init__(self,binding,manifest):
        self.binding=binding;self.manifest=manifest;self.calls=[];self.assets=[];self.draft=True;self.push=True;self.owner=True
        self.edited=False;self.comment_bad=False;self.run_success=True;self.job_bad=False;self.redirect=False;self.evil_redirect=False;self.ambiguous=False
        self.comment_time=datetime.now(timezone.utc)-timedelta(minutes=1)
        self.add(binding['canary_name'],s.probe.fixture(RUN),asset_id=binding['canary_asset_id'])
    def add(self,name,body=b'fictional',asset_id=None,size=None):
        a=dict(id=asset_id or 1000+len(self.assets),name=name,body=body,size=len(body) if size is None else size)
        self.assets.append(a);return a
    def metadata(self,a):return dict(id=a['id'],name=a['name'],size=a['size'],state='uploaded',digest='sha256:'+s.sha(a['body']),url=s.API+'/releases/assets/'+str(a['id']))
    def __call__(self,request,timeout):
        self.calls.append(request);url=request.full_url;p=urlsplit(url)
        if p.hostname in s.probe.CDN_HOSTS:
            if request.get_header('Authorization') or request.get_header('Cookie'):raise AssertionError('credential leaked to CDN')
            return Response(self.redirect_body)
        if url==o.USER_API:
            if request.get_header('Authorization')!='Bearer ghp_FICTIONAL':raise AssertionError('actual /user auth missing')
            return Response(dict(login=o.OWNER,id=o.OWNER_ID if self.owner else 1,type='User'))
        if url==s.API:return Response(dict(full_name=s.REPO,owner={'id':o.OWNER_ID},permissions={'push':self.push}))
        if url==s.API+'/issues/comments/77':
            created=self.comment_time.isoformat();return Response(dict(id=77,url=url,user={'login':o.OWNER,'id':o.OWNER_ID},author_association='OWNER',
                body='wrong' if self.comment_bad else o.authorization_body(self.manifest),created_at=created,updated_at=(datetime.now(timezone.utc).isoformat() if self.edited else created)))
        if '/actions/runs/' in url:
            rid=p.path.split('/runs/')[1].split('/')[0]
            if '/jobs' in url:
                if rid==RUN:
                    jobs=[dict(id=x['job']['api_job_id'],name=x['job']['job_id'],head_sha=SOURCE,run_id=int(RUN),status='completed',conclusion='success',
                        started_at=x['started_at_utc'],completed_at=x['created_at_utc']) for x in (self.manifest['qualification']['before_proof'],self.manifest['qualification']['read_proof'],self.manifest['qualification'])]
                    if self.job_bad:jobs[0]['head_sha']='c'*40
                else:jobs=[dict(id=999,name='restore',head_sha=CURRENT,run_id=int(RESTORE_RUN),status='in_progress')]
                return Response(dict(total_count=len(jobs),jobs=jobs))
            return Response(dict(id=int(rid),head_sha=SOURCE if rid==RUN else CURRENT,event='workflow_dispatch',run_attempt=1,
                status='completed' if rid==RUN else 'in_progress',conclusion='success' if self.run_success else 'failure',path='.github/workflows/lab.yml',
                repository={'full_name':s.REPO},head_repository={'full_name':s.REPO}))
        if request.method=='POST':
            if p.hostname!='uploads.github.com' or p.path!='/repos/'+s.REPO+'/releases/91/assets':raise AssertionError('release creation/foreign POST')
            name=parse_qs(p.query)['name'][0];a=self.add(name,request.data)
            if self.ambiguous:self.ambiguous=False;raise URLError('PRIVATE_BODY_MUST_NOT_LOG')
            return Response(self.metadata(a),201)
        if p.path.endswith('/releases/91'):return Response(dict(id=91,draft=self.draft,published_at=None if self.draft else '2026-10-24T00:00:00Z',tag_name=self.binding['tag_name'],url=s.API+'/releases/91'))
        if p.path.endswith('/releases/91/assets'):
            page=int(parse_qs(p.query).get('page',['1'])[0]);return Response([self.metadata(a) for a in self.assets[(page-1)*100:page*100]])
        if '/releases/assets/' in url:
            aid=int(p.path.rsplit('/',1)[-1]);a=next(a for a in self.assets if a['id']==aid)
            if request.get_header('Accept')=='application/octet-stream':
                if self.redirect or self.evil_redirect:
                    self.redirect_body=a['body'];host='evil.invalid' if self.evil_redirect else 'objects.githubusercontent.com'
                    return Response(b'',302,{'Location':'https://'+host+'/fictional?signed=DO_NOT_LOG'})
                return Response(a['body'])
            return Response(self.metadata(a))
        raise AssertionError('unknown fictional route '+p.path)


class Store:
    def __init__(self):self.admissions=[]
    @contextmanager
    def transaction(self):yield
    def _require(self,size):self.admissions.append(size)
    def snapshot(self):return {'physical_bytes':0}
    def write_bytes(self,path,body):Path(path).parent.mkdir(parents=True,exist_ok=True);s.create_local(path,body)
    def import_file(self,source,dest,expected_sha256):
        value=s.read_local(source,8<<20)
        if s.sha(value)!=expected_sha256:raise s.StoreError('HASH')
        self.write_bytes(dest,value)


class OwnerBootstrapChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.journal=self.root/'journal';self.journal.mkdir(mode=0o700)
        self.body=b'OPAQUE FICTIONAL MODEL BYTES, NOT A PICKLE\x80'
        self.file=self.file_record('models/fixture.bin',self.body)
        digest=s.sha(s.probe.fixture(RUN));runtime='d'*32
        self.binding=dict(schema_version='weekly-private-draft-binding-v2',repository=s.REPO,runtime_id=runtime,origin_run_id=RUN,release_id=91,
            tag_name='weekly-private-runtime-v2-'+runtime,canary_asset_id=5,canary_name='canary-'+digest+'.txt',canary_sha256=digest,canary_bytes=117,
            browser_tag='untagged-'+'e'*20,config_sha256=s.config_sha())
        self.q=qualification(self.binding);rights=dict(schema_version='weekly-owner-bootstrap-rights-review-v1',approved=True,basis='OWNER_DELEGATED_OCT24_PRIVATE_ONLY',human_review_claim=False,approved_logical_paths=[self.file['logical_path']])
        self.manifest=b.freeze([self.file],binding=self.binding,qualification=self.q,rights=rights,source_sha=SOURCE,code_pins={'fixture.py':'f'*64})
        self.server=Server(self.binding,self.manifest)
    def tearDown(self):self.temp.cleanup()
    def file_record(self,name,body,required=True):
        path=self.root/('source-'+s.sha(name.encode()));path.write_bytes(body)
        return dict(logical_path=name,path=str(path),bytes=len(body),sha256=s.sha(body),kind='model' if required else 'source_raw',required=required,
            origin=dict(source_path=str(path),source_sha256=s.sha(body),source_policy_sha256=POLICY))
    def client(self,**kw):return o.OwnerBootstrapClient('ghp_FICTIONAL',journal=self.journal,source_sha=SOURCE,transport=self.server,process=s.sha(b'owner-process'),**kw)
    def upload(self):
        body,_=b.encode(self.manifest['bundles'][0]['files']);return o.upload_one(self.client(),self.manifest,0,77,body)

    def test_separate_owner_lane_never_instantiates_or_fakes_GHA_client(self):
        with self.assertRaisesRegex(s.StoreError,'AUTOMATIC_TOKEN'):s.Client('ghp_FICTIONAL',RUN,journal=self.journal,source_sha=SOURCE,transport=self.server)
        client=self.client();self.assertIsNone(client.run_id);self.assertIsNone(client.job);self.assertEqual(client.execution_lane,'OWNER_BOOTSTRAP')
        self.assertFalse(isinstance(client,s.Client));self.assertEqual(self.server.calls,[])

    def test_actual_user_identity_and_push_permission_precede_POST(self):
        for attribute in ('owner','push'):
            setattr(self.server,attribute,False)
            with self.assertRaisesRegex(s.StoreError,'ACTUAL_OWNER'):self.upload()
            setattr(self.server,attribute,True)
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))

    def test_exact_fresh_unedited_owner_comment_is_required(self):
        for attribute in ('edited','comment_bad'):
            setattr(self.server,attribute,True)
            with self.assertRaisesRegex(s.StoreError,'OWNER_COMMENT'):self.upload()
            setattr(self.server,attribute,False)
        self.server.comment_time=datetime.now(timezone.utc)-timedelta(hours=2)
        with self.assertRaises(s.StoreError):self.upload()
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))

    def test_full_qualification_routes_and_distinct_genuine_jobs_required(self):
        for mutate in (lambda q:q['read_proof']['routes'].clear(),lambda q:q['read_proof']['routes'][0].update(status=403,resource_permission_message_exact_match=False),
            lambda q:q['job'].update(execution_lane='OWNER_BOOTSTRAP'),lambda q:q.update(process_identity=q['before_process_identity'])):
            q=deepcopy(self.q);mutate(q)
            with self.assertRaises(s.StoreError):o.archived_qualification(self.binding,q)

    def test_actual_successful_run_head_jobs_and_clock_rechecked(self):
        for attribute in ('run_success','job_bad'):
            setattr(self.server,attribute,False if attribute=='run_success' else True)
            with self.assertRaisesRegex(s.StoreError,'ACTUAL_QUALIFIED'):self.upload()
            setattr(self.server,attribute,True if attribute=='run_success' else False)
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))

    def test_owner_upload_only_private_root_payload_descriptor_assets_and_explicit_origin(self):
        descriptor=self.upload();entry=descriptor['entry']
        self.assertIsNone(entry['writer_run_id']);self.assertEqual(entry['writer_origin']['execution_lane'],'OWNER_BOOTSTRAP')
        self.assertEqual(len([r for r in self.server.calls if r.method=='POST']),3)
        self.assertNotIn('root_manifest',descriptor);self.assertNotIn(str(self.root),s.canonical(descriptor).decode())
        self.assertEqual(entry['owner_authorization_comment_id'],77);self.assertNotEqual(entry['root_manifest_sha256'],entry['payload_sha256'])
        with self.assertRaises(s.StoreError):self.client().reserve_post(s.API+'/releases','forbidden',b'x')

    def test_every_POST_reserved0600_before_transport_and_ambiguous_never_retried(self):
        real=self.server
        def checked(request,timeout):
            if request.method=='POST':
                files=list(self.journal.glob('*.reservation.json'));self.assertTrue(files)
                self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in files))
            return real(request,timeout)
        client=o.OwnerBootstrapClient('ghp_FICTIONAL',journal=self.journal,source_sha=SOURCE,transport=checked,process=s.sha(b'owner-process'));self.server.ambiguous=True
        body,_=b.encode(self.manifest['bundles'][0]['files'])
        with self.assertRaises(s.StoreError):o.upload_one(client,self.manifest,0,77,body)
        count=len([r for r in self.server.calls if r.method=='POST'])
        with self.assertRaises(s.StoreError):self.upload()
        self.assertEqual(len([r for r in self.server.calls if r.method=='POST']),count)

    def test_all_orphans_and_pending_slots_bytes_count(self):
        client=self.client();client.bind(self.binding)
        for i in range(4):self.server.add('orphan-'+str(i),size=s.ASSET_CAP)
        with self.assertRaisesRegex(s.StoreError,'RUNTIME_BYTES_CAP'):client.inventory()
        self.server.assets=self.server.assets[:1]
        for i in range(128):client.reserve('pending-'+str(i),b'x',name='missing-'+str(i))
        with self.assertRaises(s.StoreError):client.inventory()

    def test_CDN_redirect_strips_auth_and_unknown_host_fails(self):
        self.server.redirect=True;descriptor=self.upload();self.assertTrue(any(urlsplit(r.full_url).hostname in s.probe.CDN_HOSTS for r in self.server.calls))
        self.server.redirect=False;self.server.evil_redirect=True;client=self.client();client.bind(self.binding)
        with self.assertRaisesRegex(s.StoreError,'REDIRECT_FORBIDDEN'):o.verify_canary(client)
        self.assertFalse(any(urlsplit(r.full_url).hostname=='evil.invalid' for r in self.server.calls))

    def test_streaming_encoding_deterministic_and_opaque_hash_enforced(self):
        first,size=b.encode([self.file]);second,other=b.encode([self.file]);self.assertEqual(first,second);self.assertEqual(size,other)
        record=dict(bytes=len(first),sha256=s.sha(first),inflated_bytes=size,files=[self.file])
        self.assertEqual(b.verify_bundle(first,record),[(self.file['logical_path'],self.body)])
        Path(self.file['path']).write_bytes(b'changed')
        with self.assertRaises(s.StoreError):b.encode([self.file])

    def test_exact_scope_rights_and_optional_raw_pending_not_cap_growth(self):
        with self.assertRaises(s.StoreError):b.validate_files([self.file,self.file])
        with self.assertRaises(s.StoreError):b.validate_files([dict(self.file,logical_path='../outside')])
        raw=self.file_record('raw/fixture.bin',b'private-fictional-raw',False)
        rights=deepcopy(self.manifest['rights_review'])
        result=b.freeze([self.file,raw],binding=self.binding,qualification=self.q,rights=rights,source_sha=SOURCE,code_pins={'x':'f'*64})
        self.assertEqual(result['pending_raw_archive'][0]['reason'],'RAW_ARCHIVE_PENDING_RIGHTS_REVIEW')
        rights['approved_logical_paths']=[]
        with self.assertRaisesRegex(s.StoreError,'REQUIRED_RIGHTS'):b.freeze([self.file],binding=self.binding,qualification=self.q,rights=rights,source_sha=SOURCE,code_pins={'x':'f'*64})

    def test_closed_extraction_no_overwrite_or_symlink_and_original_admission(self):
        body,size=b.encode([self.file]);record=dict(bytes=len(body),sha256=s.sha(body),inflated_bytes=size,files=[self.file]);store=Store();destination=self.root/'extract'
        result=b.extract_owned(body,record,store,destination);self.assertEqual(result['model_decodes'],0);self.assertTrue(store.admissions)
        with self.assertRaises(s.StoreError):b.extract_owned(body,record,store,destination)
        target=self.root/'real';target.mkdir();link=self.root/'symlink';link.symlink_to(target,target_is_directory=True)
        with self.assertRaises(s.StoreError):b.extract_owned(body,record,store,link)

    def test_fresh_genuine_GHA_restore_verifies_owner_comment_and_remote_bytes(self):
        descriptor=self.upload();journal=self.root/'gha';journal.mkdir(mode=0o700)
        job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=CURRENT,
            job_id='restore',permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
        client=s.Client('ghs_FICTIONAL',RESTORE_RUN,journal=journal,source_sha=CURRENT,transport=self.server,job=job,process=s.sha(b'gha-fresh'))
        body,record,receipt=o.restore_owner_bundle(client,descriptor,expected_root_sha256=s.sha(s.canonical(self.manifest)),expected_comment_id=77)
        self.assertEqual(s.sha(body),record['sha256']);self.assertTrue(receipt['exact_remote_readback']);self.assertIsNone(receipt['origin_writer_run_id'])
        with self.assertRaisesRegex(s.StoreError,'GENUINE_GHA'):o.restore_owner_bundle(self.client(),descriptor,expected_root_sha256='0'*64,expected_comment_id=77)

    def test_future_relocation_preserves_original_bytes_params_and_new_SHA(self):
        model=self.root/'opaque-model';model.write_bytes(self.body);model_ref=dict(path=str(model),bytes=len(self.body),sha256=s.sha(self.body))
        original=dict(schema_version='weekly-adaptive-release-v1-future-inference',artifact_kind='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',dependencies=[],
            model=dict(model_ref,path='/old/workspace/trained.joblib'),source_contract={'source_policy_sha256':POLICY},environment={'fixture':'same'},code_pins={'x':'a'*64},procedure_version='b'*64,replay_bits_sha256='c'*64)
        raw=s.canonical(original);path=self.root/'original.json';path.write_bytes(raw);original_ref=dict(path=str(path),bytes=len(raw),sha256=s.sha(raw));store=Store()
        with patch('nfl_lab.owned_reference_batch.validate_owned_references'):
            result=b.relocate_future_manifest(original_ref,model_ref,self.root/'relocated',store)
        saved=json.loads(Path(result['path']).read_text());self.assertNotEqual(result['sha256'],original_ref['sha256']);self.assertFalse(result['old_path_hash_reproduced'])
        self.assertEqual((self.root/'relocated/original-future-inference.json').read_bytes(),raw);self.assertEqual((self.root/'relocated/trained.joblib').read_bytes(),self.body)
        for name in ('source_contract','environment','code_pins','procedure_version','replay_bits_sha256'):self.assertEqual(saved[name],original[name])

    def test_CLI_preparation_no_env_input_network_and_source_head_metadata_only(self):
        class NoEnvironment:
            def get(self,*a):raise AssertionError('credential discovery')
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['upload'],environ=NoEnvironment(),transport=lambda *a:(_ for _ in ()).throw(AssertionError('HTTP'))),2)
        self.assertEqual(json.loads(out.getvalue())['state'],'PREPARATION_ONLY_NO_IO')
        fake=self.root/'checkout';(fake/'.git').mkdir(parents=True);(fake/'.git/HEAD').write_text(SOURCE+'\n')
        self.assertEqual(cli.checkout_head(fake),SOURCE)


if __name__=='__main__':unittest.main()
