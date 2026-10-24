"""Real owner, immutable aliases and unchanged original sink/helper AST; fictional rows."""
import ast
from datetime import datetime,timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import pandas as pd

from nfl_lab import weekly_generic_producer as generic
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references

ROOT=Path(__file__).resolve().parents[1]


def original_metadata_api():
    tree=ast.parse((ROOT/'nfl_lab/weekly_future_inference.py').read_bytes())
    cdf_tree=ast.parse((ROOT/'nfl_lab/cdf_engine.py').read_bytes())
    keys=ast.literal_eval(next(n.value for n in cdf_tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='KEYS' for t in n.targets)))
    ns=dict(__name__='nfl_lab.weekly_future_inference',__package__='nfl_lab',Path=Path,BytesIO=BytesIO,hashlib=hashlib,json=json,pd=pd,require=generic.require,
        cdf=SimpleNamespace(KEYS=keys),now_utc=lambda:datetime.now(timezone.utc))
    identity=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='IDENTITY' for t in n.targets))
    nodes=[identity]+[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
        {'sha','binding','query_projection','frame_digest','persist_feature_capture'}]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_future_feature_persistence_AST','exec'),ns)
    current=ast.parse((ROOT/'nfl_lab/weekly_current_inference.py').read_bytes())
    sink_node=next(n for n in current.body if isinstance(n,ast.ClassDef) and n.name=='BoundedOutput')
    exec(compile(ast.Module(body=[sink_node],type_ignores=[]),'actual_unchanged_BoundedOutput_AST','exec'),ns)
    return ns


class OwnedFeatureBridgeChecks(unittest.TestCase):
    def test_real_owner_authentication_and_bounded_writes_reserve_and_restoration(self):
        api=original_metadata_api();BoundedOutput=api['BoundedOutput']
        policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);owner=OperationalStorage(root/'cache',policy,state=root/'state');owner.register_root(root/'inputs')
            owner.write_bytes(root/'inputs/source.bin',b'FICTIONAL_IMMUTABLE_SOURCE_ONLY')
            source=api['binding'](root/'inputs/source.bin');output=owner.register_root(root/'output')
            sink=BoundedOutput(owner,output,4<<20)
            frame=pd.DataFrame([dict(season=2026,week=7,game_id='FICTIONAL_GAME',player_id='FICTIONAL_PLAYER',team='A',opponent='B',position='QB',
                kickoff_utc='2026-10-25T13:30:00+00:00',cutoff_utc='2026-10-25T00:00:00+00:00',
                feature_max_source_available_utc='2026-10-24T00:00:00+00:00',f_fixture=1.0)])
            self.assertNotIn('write_bytes',owner.__dict__)
            with generic.owned_feature_output(owner,sink) as authentic_owner:
                self.assertIs(authentic_owner,owner)
                for name in ('queries','quarantine','no_remaining_game'):
                    authentic_owner.write_dataframe(frame,output/(name+'.parquet'),index=False)
                feature_ref,capture_ref=api['persist_feature_capture'](output/'features.parquet',frame,features=['f_fixture'],
                    source_contract={'availability_rule':'FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION'},source_bindings=[source],storage=authentic_owner)
            self.assertIs(sink.storage,owner);self.assertNotIn('write_bytes',owner.__dict__)
            validate_owned_references(owner,{r['path']:r['sha256'] for r in [source,feature_ref,capture_ref]})
            self.assertEqual(len(list(output.glob('*.parquet'))),4)
            self.assertFalse((Path(source['path']).stat().st_mode)&0o222)
            other=OperationalStorage(root/'other-cache',policy,state=root/'other-state')
            with self.assertRaisesRegex(ValueError,'exact genuine storage owner'):
                with generic.owned_feature_output(other,sink):pass
            self.assertIs(sink.storage,owner);self.assertNotIn('write_bytes',other.__dict__)
            limited_root=owner.register_root(root/'limited');limited=BoundedOutput(owner,limited_root,BoundedOutput.RESERVE+1)
            with self.assertRaisesRegex(ValueError,'byte ceiling'):
                with generic.owned_feature_output(owner,limited):owner.write_dataframe(frame,limited_root/'queries.parquet',index=False)
            self.assertFalse((limited_root/'queries.parquet').exists())
            self.assertIs(limited.storage,owner);self.assertNotIn('write_bytes',owner.__dict__)
            prior=lambda *a,**k:(_ for _ in ()).throw(OSError('FICTIONAL_WRITE_FAILURE'))
            owner.write_bytes=prior
            try:
                with self.assertRaises(OSError):
                    with generic.owned_feature_output(owner,sink):owner.write_bytes(output/'failed.bin',b'x')
                self.assertIs(owner.__dict__['write_bytes'],prior);self.assertIs(sink.storage,owner)
                self.assertEqual(sink.unpublished,1)
            finally:owner.__dict__.pop('write_bytes',None)


if __name__=='__main__':unittest.main()
