"""Ten new fictional/mock reporting contracts; no NFL values or aggregation."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from baseline_correction_run import extension
extension({"path":str(ROOT/"nfl_lab/baseline_correction.py"),
    "sha256":"077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2"})
spec=importlib.util.spec_from_file_location("fictional_correction_reporting",ROOT/"tools/baseline_correction_report_v2.py")
subject=importlib.util.module_from_spec(spec);spec.loader.exec_module(subject)


def categories():
    return {target:{"state":"BLOCKED" if target=="fantasy_ppr" else "READY"}
        for target in subject.shared.models.TARGETS}


def frozen():
    slots=[];scored=[];bindings={}
    for year in subject.shared.YEARS:
        for target in subject.shared.models.TARGETS:
            if target=="fantasy_ppr":continue
            for method in subject.METHODS:
                row=dict(year=year,target=target,method=method,rows={2022:8686,2023:8606,2024:8580}[year],
                    forecast=f"private/forecasts/{year}/{target}/{method}.parquet",state="FICTIONAL_METADATA_ONLY")
                name=f"private/scored/{year}/{target}/{method}.parquet"
                slots.append(row);scored.append(dict(row,scored=name));bindings[name]="a"*64
    return dict(slots=slots),dict(slots=scored,bindings=bindings)


class ReportingContracts(unittest.TestCase):
    def test_exact_four_seven_partition_and_PPR_block(self):
        plan=subject.work_plan(categories())
        self.assertEqual(sum(x=="REUSE_EXACT_BYTES" for x in plan.values()),4)
        self.assertEqual(sum(x=="AGGREGATE_FROZEN_ROWS" for x in plan.values()),7)
        self.assertEqual(plan["fantasy_ppr"],"BLOCKED_EXACT_PPR")
        bad=categories();bad["fantasy_ppr"]["state"]="READY"
        with self.assertRaises(ValueError):subject.work_plan(bad)

    def test_complete66_slot_sequence_and_no_extra_scored_file(self):
        forecast,scored=frozen();scope={"parent_root":"/tmp/fictional-correction-parent"}
        self.assertEqual(len(subject.frozen_slot_paths(scope,forecast,scored)),66)
        scored["slots"].pop()
        with self.assertRaises(ValueError):subject.frozen_slot_paths(scope,forecast,scored)
        forecast,scored=frozen();scored["bindings"]["private/scored/unregistered.parquet"]="a"*64
        with self.assertRaises(ValueError):subject.frozen_slot_paths(scope,forecast,scored)

    def test_all165_five_controls_required(self):
        names=[f"private/scored/{year}/{target}/{method}/rows.parquet"
            for year in subject.shared.YEARS for target in subject.REUSE+subject.REMAINING for method in subject.parent.CONTROLS]
        meta=dict(scored_files=names,bindings={name:"b"*64 for name in names})
        self.assertEqual(len(subject.control_paths({"control_root":"/tmp/fictional-controls"},meta)),165)
        meta["scored_files"].pop()
        with self.assertRaises(ValueError):subject.control_paths({"control_root":"/tmp/fictional-controls"},meta)

    def test_complete_target_reuse_is_byte_alias_not_aggregation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"complete.json";path.write_text('{"target":"pass_yd","pairs":[],"research_nominations":[]}\n')
            files={key:dict(path=str(path),sha256="c"*64) for key in ("report","pairs","subgroups")}
            session=SimpleNamespace(storage=SimpleNamespace(import_file=Mock()),output=Path(folder)/"new",
                authenticated_controls={str(path):{"sha256":"c"*64}},bindings={})
            with patch.object(subject.parent,"target_report",side_effect=AssertionError("no repeated aggregation")):
                result=subject.reuse_target(session,"pass_yd",files)
            self.assertEqual(result["target"],"pass_yd");self.assertEqual(session.storage.import_file.call_count,3)
            self.assertEqual(session.bindings["target-reports/pass_yd.json"],"c"*64)

    def test_completed_target_cannot_enter_aggregation(self):
        with patch.object(subject.pd,"read_parquet",side_effect=AssertionError("no private reused decode")):
            with self.assertRaises(ValueError):subject.aggregate_target(None,"pass_att",{},[])

    def test_missing_target_calls_only_original_report_helpers_with_mocks(self):
        import pandas as pd
        slots=[dict(year=y,target="pass_int",method=m,scored=f"private/scored/{y}/pass_int/{m}.parquet")
            for y in subject.shared.YEARS for m in subject.METHODS]
        session=SimpleNamespace(spec={"parent_root":"/tmp/fictional-parent"},check=Mock(),frame=Mock(),write=Mock())
        frame=pd.DataFrame({"fictional":[0]});report={"target":"pass_int"}
        with patch.object(subject.pd,"read_parquet",return_value=frame), \
                patch.object(subject.parent,"_control",return_value=frame) as controls, \
                patch.object(subject.parent,"target_report",return_value=(report,frame)) as aggregate, \
                patch.object(subject.original_correction,"later_descriptive_pairs",return_value=[]) as later, \
                patch.object(subject.parent,"subgroup_rows",return_value=frame) as groups:
            subject.aggregate_target(session,"pass_int",{"target":"pass_int"},slots)
        self.assertEqual((aggregate.call_count,later.call_count,groups.call_count,controls.call_count),(1,1,1,15))
        self.assertEqual(session.frame.call_count,2);self.assertEqual(session.write.call_count,1)

    def test_decode_allowlist_excludes_reused_queries_and_models(self):
        _,scored=frozen();scope={"parent_root":"/tmp/fictional-parent","control_root":"/tmp/fictional-controls"}
        with patch.object(subject.pd,"read_parquet",return_value="fictional") as read:
            with subject.frozen_reads_only(scope,scored):
                good="/tmp/fictional-parent/private/scored/2022/pass_int/cdf_offset_intercept_v1.parquet"
                self.assertEqual(subject.pd.read_parquet(good),"fictional")
                for path in ("/tmp/fictional-parent/private/scored/2022/pass_yd/cdf_offset_intercept_v1.parquet",
                        "/tmp/fictional-parent/private/queries/2024.parquet","/tmp/fictional-model.joblib"):
                    with self.assertRaises(AssertionError):subject.pd.read_parquet(path)
        self.assertEqual(read.call_count,1)

    def test_report_only_guards_block_scoring_correction_and_label_routes(self):
        with subject.report_only():
            for owner,name in ((subject.parent.direct,"score_frozen_rows"),
                    (subject.original_correction,"labels_from"),
                    (subject.original_correction.correction.BaselineCorrection,"predict"),
                    (subject.original_correction.correction.BaselineCorrection,"fit"),
                    (subject.shared.cdf.LeafCDFModel,"predict_batches")):
                with self.assertRaises(AssertionError):getattr(owner,name)()

    def test_matrix_copies_existing_cells_without_new_numeric_work(self):
        pairs=[dict(period="pooled_2022_2024",population="primary_roles",fictional=1),
            dict(period=2024,population="primary_roles",fictional=2)]
        report=dict(pairs=pairs,research_nominations=[{"fictional":"unchanged"}])
        session=SimpleNamespace(bindings={"target-reports/pass_yd.json":"d"*64})
        result=subject.matrix_record(session,"pass_yd",report)
        self.assertEqual(result["pooled_primary_pairs"],[pairs[0]])
        self.assertIs(result["research_nominations"],report["research_nominations"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(subject.matrix_record(session,"fantasy_ppr",None)["state"],"BLOCKED_EXACT_PPR")

    def test_unchanged_guard_budgets_and_parent_failure_contract_are_explicit(self):
        config=json.loads((ROOT/"config/baseline-correction-report-v2.json").read_text())
        self.assertEqual(config["budgets"]["new_retained_bytes"],16777216)
        self.assertEqual(config["budgets"]["combined_RSS_bytes"],1073741824)
        self.assertEqual(config["budgets"]["wall_seconds"],600)
        source=(ROOT/"tools/baseline_correction_report_supervisor_v2.py").read_text()
        self.assertIn('cpu>=595',source);self.assertIn('"600s"',source)
        self.assertIn('1073741824-24*1024**2',source);self.assertIn('worker_start_ticks=worker_start',source)
        self.assertIn('terminal["limit_reason"] != "CPU_LIMIT"',(ROOT/"tools/baseline_correction_report_v2.py").read_text())


if __name__=="__main__":unittest.main()
