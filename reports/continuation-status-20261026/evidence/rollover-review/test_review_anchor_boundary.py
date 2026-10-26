"""Read-only review probe: stop before any fictional private bytes are read."""
import json
from test_audit_weekly_grade_history_v1 import original_seed, locator_seed, no_network, recovery_case, history
from test_private_draft_store_v2 import Response

class StopBeforePrivateBytes(RuntimeError):
    pass

def test_observe_anchor_authentication_before_private_get(tmp_path,locator_seed,monkeypatch):
    x=recovery_case(tmp_path/"new-reader",locator_seed,monkeypatch,role="produce",current_run="45000000003")
    from copy import deepcopy
    from datetime import timedelta
    import gzip
    from nfl_lab import private_draft_store as store,state,gha_private_checkpoint as cp
    raw=gzip.compress(store.canonical(locator_seed['locator']),mtime=0)
    path=tmp_path/'new-reader/locator.json.gz';x.storage.write_bytes(path,raw);x.sidecar=cp.binding(path)
    root=deepcopy(locator_seed['original_root']);root['issued_at_utc']=locator_seed['current_at']
    root['expires_at_utc']=(state.utc(root['issued_at_utc'])+timedelta(hours=1)).isoformat()
    root['effective_epoch']['previous_checkpoint']=dict(schema_version=history.LOCATOR_REF,path=history.locator_filename(locator_seed['locator']),sha256=store.sha(raw))
    x.context.go=root
    anchor=locator_seed["receipt"]["run_id"]
    cohort=locator_seed["sidecar"]["run_id"]
    assert anchor!=cohort
    actual=x.api
    observed=[]
    def api(request,timeout):
        url=request.full_url
        observed.append(url)
        if "/actions/runs/"+anchor in url:
            return Response(dict(id=int(anchor),status="completed",conclusion="failure",run_attempt=2))
        if "/releases/" in url:
            raise StopBeforePrivateBytes("PRIVATE_GET_BOUNDARY_REACHED")
        return actual(request,timeout)
    try:
        history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=api)
    except StopBeforePrivateBytes:
        pass
    else:
        raise AssertionError("Expected stop at first private-namespace request")
    anchor_gets=[u for u in observed if "/actions/runs/"+anchor in u]
    cohort_gets=[u for u in observed if "/actions/runs/"+cohort in u]
    result=dict(kind="OFFLINE_FICTIONAL_BOUNDARY_OBSERVATION_NOT_NATIVE_QUALIFICATION",anchor_run=anchor,cohort_run=cohort,
        anchor_run_requests=len(anchor_gets),cohort_run_requests=len(cohort_gets),private_namespace_request_reached=True,private_bytes_read=0)
    (tmp_path.parent.parent/"anchor-authentication-observation.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True))
    assert not anchor_gets and cohort_gets
