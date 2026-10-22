from datetime import timedelta

from nfl_lab.state import append_outcomes, records, resolved_outcomes
from test_lab_state import NOW, observation


KEY=("p","g","rec")


def test_unrelated_feed_versions_preserve_first_unknown_clock_receipt(tmp_path):
    first=dict(observation(0),status_sha256="first-status",finality="completed")
    assert append_outcomes(tmp_path,[first])=={"appended":1}
    path=next((tmp_path/"outcomes").glob("*.json.gz"));body=path.read_bytes()
    for version in range(100):
        changed=dict(first,source_sha256=f"whole-feed-{version}",status_sha256=f"status-{version}",
                     observed_at=(NOW+timedelta(days=version+1)).isoformat(),finality="new unrelated game final")
        assert append_outcomes(tmp_path,[changed])=={"appended":0}
    assert list(records(tmp_path,"outcomes"))==[first]
    assert list((tmp_path/"outcomes").glob("*.json.gz"))==[path]
    assert path.read_bytes()==body


def test_played_missing_to_supported_zero_is_a_new_observation(tmp_path):
    assert append_outcomes(tmp_path,[observation(None)])=={"appended":1}
    assert append_outcomes(tmp_path,[observation(0)])=={"appended":1}
    assert resolved_outcomes(tmp_path)[KEY]=={"state":"played","actual":0}
    assert len(list(records(tmp_path,"outcomes")))==2
    assert append_outcomes(tmp_path,[observation(0.0)])=={"appended":0}


def test_origins_and_participation_remain_distinct(tmp_path):
    first=observation(1)
    second=dict(first,source="another-origin",source_sha256="another-body")
    assert append_outcomes(tmp_path,[first,second])=={"appended":2}
    assert append_outcomes(tmp_path,[dict(second,actual=2)])=={"appended":1}
    assert resolved_outcomes(tmp_path)[KEY]["state"]=="unresolved_numeric_conflict"
    assert append_outcomes(tmp_path,[observation(None,"DNP")])=={"appended":1}
    assert resolved_outcomes(tmp_path)[KEY]["state"]=="unresolved_participation_conflict"


def test_unknown_clock_reversions_never_establish_correction_order(tmp_path):
    a=observation(1);b=dict(observation(2),observed_at=(NOW+timedelta(days=1)).isoformat())
    assert append_outcomes(tmp_path,[a,b])=={"appended":2}
    assert append_outcomes(tmp_path,[dict(a,source_sha256="later-body",observed_at=(NOW+timedelta(days=2)).isoformat())])=={"appended":0}
    assert resolved_outcomes(tmp_path)[KEY]=={"state":"unresolved_numeric_conflict","actual":None}


def test_known_clock_correction_and_reversion_retains_each_version(tmp_path):
    a=dict(observation(1),source_timestamp="2026-10-22T01:00:00Z")
    b=dict(observation(2),source_timestamp="2026-10-22T02:00:00Z")
    reversion=dict(a,source_timestamp="2026-10-22T03:00:00Z",source_sha256="reverted-body")
    assert append_outcomes(tmp_path,[a,b,reversion])=={"appended":3}
    assert append_outcomes(tmp_path,[dict(reversion,observed_at=(NOW+timedelta(days=1)).isoformat())])=={"appended":0}
    assert resolved_outcomes(tmp_path)[KEY]=={"state":"played_corrected","actual":1}


def test_known_clock_same_value_versions_preserve_out_of_order_resolution(tmp_path):
    a=dict(observation(1),source_timestamp="2026-10-22T01:00:00Z")
    later_a=dict(a,source_timestamp="2026-10-22T03:00:00Z",source_sha256="later-a")
    late_arrival_b=dict(observation(2),source_timestamp="2026-10-22T02:00:00Z")
    assert append_outcomes(tmp_path,[a,later_a])=={"appended":2}
    assert append_outcomes(tmp_path,[late_arrival_b])=={"appended":1}
    assert resolved_outcomes(tmp_path)[KEY]=={"state":"played_corrected","actual":1}


def test_equal_authoritative_clocks_with_contradictory_values_stay_quarantined(tmp_path):
    a=dict(observation(1),source_timestamp="2026-10-22T01:00:00Z")
    b=dict(observation(2),source_timestamp=a["source_timestamp"])
    append_outcomes(tmp_path,[a,b])
    assert resolved_outcomes(tmp_path)[KEY]=={"state":"unresolved_numeric_conflict","actual":None}


def test_distinct_scoring_bindings_are_not_collapsed(tmp_path):
    a=dict(observation(1),scoring_id="original")
    b=dict(a,scoring_id="another-version")
    assert append_outcomes(tmp_path,[a,b])=={"appended":2}


def test_distinct_integer_values_are_not_collapsed_by_float_rounding(tmp_path):
    assert append_outcomes(tmp_path,[observation(2**53),observation(2**53+1)])=={"appended":2}
    assert resolved_outcomes(tmp_path)[KEY]["state"]=="unresolved_numeric_conflict"


def test_unclocked_repeated_old_value_still_blocks_known_clock_resolution(tmp_path):
    a=dict(observation(1),source_timestamp="2026-10-22T01:00:00Z")
    b=dict(observation(2),source_timestamp="2026-10-22T02:00:00Z")
    append_outcomes(tmp_path,[a,b])
    assert resolved_outcomes(tmp_path)[KEY]["actual"]==2
    assert append_outcomes(tmp_path,[observation(1)])=={"appended":1}
    assert resolved_outcomes(tmp_path)[KEY]["state"]=="unresolved_numeric_conflict"


def test_identity_quarantine_is_not_deduplicated_into_old_missing_record(tmp_path):
    append_outcomes(tmp_path,[observation(None),observation(2)])
    assert append_outcomes(tmp_path,[dict(observation(None),identity_quarantined=True)])=={'appended':1}
    assert resolved_outcomes(tmp_path)[KEY]['state']=='unresolved_identity_conflict'
