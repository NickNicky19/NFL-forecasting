"""Fictional contracts; actual numerical research is a separate evidence lane."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from nfl_lab.research_passing import METHOD, SourceDocument, evaluate, pooled_point


def fixture():
    context = dict(player_id="synthetic", game_id="future", team="A", opponent="B", season=2000,
                   season_type="REG", week=5, period="full_game_with_ot", cutoff_at="2000-10-22T12:00:00Z",
                   kickoff_at="2000-10-22T17:00:00Z", projection_observed_at="2000-10-22T11:00:00Z",
                   website_yards=40.5, website_attempts=20.5, baseline_receipt_sha256="a"*64,
                   projection_source_ref="fictional-original")
    header = {k: context[k] for k in ("player_id", "season", "season_type", "period")}
    schedule = dict(**header, through_week=4, weeks=[])
    stats = dict(**header, records=[])
    for week, attempts, yards in [(1, 10, 50), (2, 2, 20), (3, 4, 12), (4, 10, 60)]:
        game = dict(week=week, state="game", game_id=f"g{week}", team="A", opponent="C",
                    kickoff_at=f"2000-10-{week:02}T17:00:00Z", completed=True,
                    final_observed_at=f"2000-10-{week:02}T23:00:00Z")
        schedule['weeks'].append(game)
        stats['records'].append(dict(**header, **{k:game[k] for k in ('week','game_id','team','opponent','kickoff_at')},
                                     pass_att=attempts, pass_yd=yards, participation="played",
                                     stats_observed_at=f"2000-10-{week:02}T23:10:00Z", source_ref="fictional-stats"))
    projection = {**context, 'attempts_origin': 'same_receipt_unchanged_website'}
    return context, schedule, stats, projection


def evaluate_fixture(parts=None, mutate=None):
    context, schedule, stats, projected = parts or fixture()
    documents={}
    pins={}
    for name,ref,payload in [('opportunities','fictional-schedule',schedule),('statistics','fictional-stats',stats),('projection','fictional-original',projected)]:
        observed=context['projection_observed_at'] if name=='projection' else '2000-10-21T12:00:00Z'
        document=SourceDocument(ref,json.dumps(payload).encode(),observed)
        documents[name]=document;pins[ref]=hashlib.sha256(document.payload).hexdigest()
    if mutate:mutate(documents)
    return evaluate(context,**documents,trusted_hashes=pins),documents,pins


def test_pooled_not_average_ratio_and_fractional_held_attempts():
    result,_,_=evaluate_fixture()
    assert result.point == 20.5*92/16
    assert result.history_game_ids == ('g4','g3','g2')
    assert result.point != 20.5*((60/10+12/4+20/2)/3)
    assert result.state=='CANDIDATE_ARITHMETIC' and not result.original_runner_reproduced
    assert result.calculation_lane=='RETROSPECTIVE_ARITHMETIC' and not result.recorded_pregame


def test_signed_yards_no_floor_and_zero_held_projection():
    parts=fixture()
    for r in parts[2]['records']:r['pass_yd']=-10
    assert evaluate_fixture(parts)[0].point < 0
    parts[0]['website_attempts']=parts[3]['website_attempts']=0
    assert evaluate_fixture(parts)[0].point==0


@pytest.mark.parametrize('bad',[None,True,-1,1.5,float('nan'),float('inf')])
def test_invalid_selected_count_never_skipped_or_filled(bad):
    parts=fixture();parts[2]['records'][2]['pass_att']=bad
    result,_,_=evaluate_fixture(parts)
    assert result.state=='UNCHANGED_WEBSITE_FALLBACK' and result.point==40.5


def test_zero_attempt_pair_original_rule_and_positive_denominator():
    parts=fixture();parts[2]['records'][2].update(pass_att=0,pass_yd=1)
    assert evaluate_fixture(parts)[0].reason=='zero_attempt_nonzero_passing_yards'
    parts[2]['records'][2]['pass_yd']=0
    assert evaluate_fixture(parts)[0].state=='CANDIDATE_ARITHMETIC'
    for r in parts[2]['records']:r.update(pass_att=0,pass_yd=0)
    assert evaluate_fixture(parts)[0].reason=='nonpositive_pooled_attempts'


@pytest.mark.parametrize('kind',['unknown','missing','missing_yards','different_team','not_rostered'])
def test_intervening_gap_trade_or_missing_statistic_stops(kind):
    parts=fixture()
    if kind=='unknown':parts[2]['records'][2]['participation']='unknown'
    elif kind=='missing':parts[2]['records'].pop(2)
    elif kind=='missing_yards':parts[2]['records'][2].pop('pass_yd')
    elif kind=='different_team':parts[1]['weeks'][2]['team']='D'
    else:parts[1]['weeks'][2]['state']='not_rostered'
    result,_,_=evaluate_fixture(parts);assert result.state=='UNCHANGED_WEBSITE_FALLBACK' and result.point==40.5


def test_dnp_skips_but_zero_appearance_counts_and_older_unknown_irrelevant():
    parts=fixture();parts[2]['records'][2]['participation']='dnp'
    assert evaluate_fixture(parts)[0].history_game_ids==('g4','g2','g1')
    parts=fixture();parts[2]['records'][2].update(pass_att=0,pass_yd=0)
    assert evaluate_fixture(parts)[0].history_game_ids==('g4','g3','g2')
    parts[2]['records'][0]['participation']='unknown'
    assert evaluate_fixture(parts)[0].state=='CANDIDATE_ARITHMETIC'


def test_bye_short_history_and_complete_sequence():
    parts=fixture();parts[1]['weeks'][3].update(state='bye',game_id=None)
    assert evaluate_fixture(parts)[0].history_game_ids==('g3','g2','g1')
    parts[1]['weeks'].pop(0)
    assert evaluate_fixture(parts)[0].reason=='missing_or_duplicate_prior_week'
    parts=fixture();parts[0]['week']=parts[3]['week']=1;parts[1].update(through_week=0,weeks=[])
    assert evaluate_fixture(parts)[0].reason=='exactly_three_selected_appearances_required'


@pytest.mark.parametrize('kind',['hash','late','reconstructed','bad_pointer'])
def test_history_pin_clock_and_source_pointer_fail_to_literal_fallback(kind):
    parts=fixture()
    if kind=='bad_pointer':parts[2]['records'][3]['source_ref']='different'
    def mutate(docs):
        d=docs['statistics']
        docs['statistics']=SourceDocument(d.reference,d.payload+(b' ' if kind=='hash' else b''),
            '2000-10-23T12:00:00Z' if kind=='late' else d.observed_at,
            'current_vintage_download' if kind=='reconstructed' else d.time_basis)
    result,_,_=evaluate_fixture(parts,mutate);assert result.point==40.5 and result.state=='UNCHANGED_WEBSITE_FALLBACK'


@pytest.mark.parametrize('kind',['original_yards','other_attempt_model','wrong_identity','late_projection'])
def test_untrusted_original_source_abstains(kind):
    parts=fixture()
    if kind=='original_yards':parts[0]['website_yards']=parts[3]['website_yards']=None
    elif kind=='other_attempt_model':parts[3]['attempts_origin']='attempts_challenger'
    elif kind=='wrong_identity':parts[3]['player_id']='other'
    else:parts[0]['projection_observed_at']=parts[3]['projection_observed_at']='2000-10-23T12:00:00Z'
    result,_,_=evaluate_fixture(parts);assert result.point is None and result.state=='ABSTAIN'


def test_replay_is_pure_and_schema_does_not_invent_operational_mean():
    parts=fixture();before=copy.deepcopy(parts);a,_,_=evaluate_fixture(parts);b,_,_=evaluate_fixture(parts)
    assert parts==before and a.point==b.point and a.input_sha256==b.input_sha256
    schema=json.loads(Path('schemas/research-point-v1.json').read_text())
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(a.to_dict())
    bad=a.to_dict();bad['qualified_for_default']=True
    with pytest.raises(Exception):Draft202012Validator(schema).validate(bad)


def test_cli_explicit_method_and_create_only_output(tmp_path):
    parts=fixture();_,docs,pins=evaluate_fixture(parts)
    bundle={'context':parts[0],**{k:{'reference':d.reference,'payload':d.payload.decode(),'observed_at':d.observed_at,'time_basis':d.time_basis} for k,d in docs.items()}}
    source=tmp_path/'bundle.json';source.write_text(json.dumps(bundle));pinfile=tmp_path/'pins.json';pinfile.write_text(json.dumps(pins));out=tmp_path/'result.json'
    command=[sys.executable,'-m','nfl_lab.research_passing','--method',METHOD,'--bundle',str(source),'--pins',str(pinfile),'--output',str(out)]
    subprocess.run(command,check=True,capture_output=True)
    assert json.loads(out.read_text())['point']==20.5*92/16
    second=subprocess.run(command,capture_output=True);assert second.returncode!=0 and b'FileExistsError' in second.stderr
    assert subprocess.run([sys.executable,'-m','nfl_lab.research_passing','--bundle',str(source),'--pins',str(pinfile)],capture_output=True).returncode!=0


def test_input_identity_binds_clocks_time_basis_roles_and_trusted_pins():
    original,_,_=evaluate_fixture()
    for change in ['late','time_basis']:
        def mutate(docs):
            d=docs['statistics'];docs['statistics']=SourceDocument(d.reference,d.payload,
                '2000-10-23T12:00:00Z' if change=='late' else d.observed_at,
                'current_vintage_download' if change=='time_basis' else d.time_basis)
        changed,_,_=evaluate_fixture(mutate=mutate)
        assert changed.state=='UNCHANGED_WEBSITE_FALLBACK' and changed.input_sha256!=original.input_sha256
    parts=fixture();_,docs,pins=evaluate_fixture(parts)
    pins['additional_trusted_reference']='b'*64
    changed=evaluate(parts[0],**docs,trusted_hashes=pins)
    assert changed.point==original.point and changed.input_sha256!=original.input_sha256


def test_no_operational_default_registry_or_daily_route_added():
    from nfl_lab.models import METHODS
    assert METHOD not in METHODS
    config=json.loads(Path('config/research.json').read_text())
    assert config['operations']['default_daily_methods']==['recent','pooled']
    assert METHOD not in config['candidate_families']


def test_independent_final_poll_time_is_not_a_fabricated_actual_game_end():
    parts=fixture();parts[2]['records'][3]['stats_observed_at']='2000-10-04T22:00:00Z'
    assert evaluate_fixture(parts)[0].state=='CANDIDATE_ARITHMETIC'
    parts[1]['weeks'][3]['final_observed_at']='2000-10-23T12:00:00Z'
    assert evaluate_fixture(parts)[0].state=='UNCHANGED_WEBSITE_FALLBACK'


def test_unavailable_held_projection_preserves_trusted_original_yard_fallback():
    for value in [None,-1,True]:
        parts=fixture();parts[0]['website_attempts']=parts[3]['website_attempts']=value
        result,_,_=evaluate_fixture(parts)
        assert result.state=='UNCHANGED_WEBSITE_FALLBACK' and result.point==40.5
    parts=fixture();parts[0].pop('website_attempts');parts[3].pop('website_attempts')
    assert evaluate_fixture(parts)[0].point==40.5
