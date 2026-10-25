#!/usr/bin/env python3
"""Prepare review-only diffs; validate them on temporary source copies.

Never applies a patch to a website worktree, changes its Git ref/index, or updates
an evidence/source pin. Changing a closed engine needs a separately versioned
owner integration; these patches are not a deployable Phase2 engine registration.
"""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import argparse

sys.dont_write_bytecode = True
AUDIT = Path(os.environ.get("NFL_AUDIT_ROOT", Path(__file__).resolve().parent))

ISSUED = '''def preserve_issued_record(path):
    """Keep exact previously issued bytes before a caller replaces its pointer.

    Original grading versions and historical results remain inside their
    original bytes. These snapshots are prior publications, not new forecasts.
    A corrupt existing history object fails before the live pointer is written.
    Temporary partial writes never occupy the final content-addressed path.
    """
    path = Path(path)
    if not path.exists():
        return None
    issued = path.read_bytes()
    target = path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".issued-grading-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(issued)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or target.read_bytes() != issued:
                raise ValueError("Previously issued grading history checksum mismatch")
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return target


'''

REGRESSIONS = '''"""Fictional identity/version migration checks; only temporary fixture writes."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "pull"), str(ROOT / "tools")]
import build
import grade

EXPECTED_VERSION = "__VERSION__"
OLD_VERSION = "__OLD_VERSION__"


def fixture():
    prop = dict(key="rec", line=4.5, adj=6, proj=6, source="model", line_from="dk", lean="over")
    player = dict(id="fictional-player", name="Fictional Receiver", team="AAA", opp="BBB", pos="WR",
                  game_id="fictional-game", props=[prop], proj_ppr=12)
    pick = dict(prop, player_id=player["id"], game_id=player["game_id"])
    archive = dict(season=2099, week=1, players=[player], picks={"over": [pick], "under": []},
        games=[dict(id=player["game_id"], home="AAA", away="BBB", kickoff="2099-01-01T00:00:00Z")])
    stats = {player["id"]: dict(team="AAA", opp="BBB", stats={"gp": 1, "rec": 6})}
    return archive, stats


class IdentityV3Tests(unittest.TestCase):
    def test_new_version_is_explicit_on_week_and_issued_report(self):
        self.assertEqual(grade.GRADING_VERSION, EXPECTED_VERSION)
        archive, stats = fixture()
        week = grade.grade_week(archive, stats, {"fictional-game"})
        self.assertEqual(week["grading_version"], EXPECTED_VERSION)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "archive.json").write_text(json.dumps(archive))
            issued = grade.grade_all(path, lambda *args: stats, (2099, 1), {"fictional-game"})
            self.assertEqual(issued["grading_version"], EXPECTED_VERSION)
            self.assertEqual(issued["weeks"][0]["grading_version"], EXPECTED_VERSION)

    def test_valid_same_game_and_wrong_team_opponent_are_distinct(self):
        archive, stats = fixture()
        self.assertEqual(grade.grade_week(archive, stats, {"fictional-game"})["top_over"]["hit"], 1)
        for field in ("team", "opp"):
            wrong = copy.deepcopy(stats)
            wrong["fictional-player"][field] = "OTHER"
            report = grade.grade_week(archive, wrong, {"fictional-game"})
            self.assertEqual(report["top_over"]["unresolved"], 1)
            self.assertEqual(report["leans"]["unresolved"], 1)

    def test_top_pick_game_cannot_borrow_another_player_game_statistic(self):
        archive, stats = fixture()
        archive["picks"]["over"][0]["game_id"] = "other-game"
        report = grade.grade_week(archive, stats, {"fictional-game", "other-game"})
        self.assertEqual(report["top_over"]["unresolved"], 1)

    def test_builder_preserves_previously_issued_bytes_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            old = ('{ "grading_version": "' + OLD_VERSION + '", "issued": "fictional" }\\n').encode()
            path.write_bytes(old)
            build.dump(path, {"grading_version": EXPECTED_VERSION, "issued": "new-fictional"})
            target = path.parent / "grading-history" / (hashlib.sha256(old).hexdigest() + ".json")
            self.assertEqual(target.read_bytes(), old)
            self.assertEqual(json.loads(target.read_bytes())["grading_version"], OLD_VERSION)
            self.assertEqual(json.loads(path.read_bytes())["grading_version"], EXPECTED_VERSION)

    def test_each_issued_revision_is_retained_without_relabeling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            build.dump(path, {"grading_version": EXPECTED_VERSION, "actual": 4})
            first = path.read_bytes()
            build.dump(path, {"grading_version": EXPECTED_VERSION, "actual": 5})
            second = path.read_bytes()
            build.dump(path, {"grading_version": EXPECTED_VERSION, "actual": 6})
            for issued in (first, second):
                self.assertEqual((path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")).read_bytes(), issued)
            grade.preserve_issued_record(path)
            count = len(list((path.parent / "grading-history").glob("*.json")))
            grade.preserve_issued_record(path)
            self.assertEqual(len(list((path.parent / "grading-history").glob("*.json"))), count)

    def test_corrupt_history_fails_before_replacing_issued_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            issued = b'{"grading_version":"statistical-v2","issued":"fictional"}'
            path.write_bytes(issued)
            target = path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")
            target.parent.mkdir()
            target.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertEqual(path.read_bytes(), issued)

    def test_partial_write_never_occupies_final_path_and_retry_succeeds(self):
        real_fdopen = grade.os.fdopen
        class InterruptedWriter:
            def __init__(self, fd, mode):
                self.stream = real_fdopen(fd, mode)
            def __enter__(self):
                self.stream.__enter__()
                return self
            def write(self, value):
                self.stream.write(value[:7])
                self.stream.flush()
                raise OSError("FICTIONAL_INTERRUPTED_PARTIAL_WRITE")
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            issued = json.dumps(dict(grading_version=OLD_VERSION, issued="fictional-original")).encode()
            path.write_bytes(issued)
            target = path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")
            with patch.object(grade.os, "fdopen", side_effect=InterruptedWriter):
                with self.assertRaisesRegex(OSError, "FICTIONAL_INTERRUPTED_PARTIAL_WRITE"):
                    build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertEqual(path.read_bytes(), issued)
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.iterdir()), [])
            build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertEqual(target.read_bytes(), issued)
            self.assertEqual(json.loads(path.read_bytes())["grading_version"], EXPECTED_VERSION)

    def test_fsync_interruption_publishes_nothing_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            issued = json.dumps(dict(grading_version=OLD_VERSION, issued="fictional-original")).encode()
            path.write_bytes(issued)
            target = path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")
            with patch.object(grade.os, "fsync", side_effect=OSError("FICTIONAL_FSYNC_INTERRUPTION")):
                with self.assertRaisesRegex(OSError, "FICTIONAL_FSYNC_INTERRUPTION"):
                    build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertEqual(path.read_bytes(), issued)
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.iterdir()), [])
            build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertEqual(target.read_bytes(), issued)

    def test_symlink_history_collision_does_not_rewrite_any_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track_record.json"
            issued = json.dumps(dict(grading_version=OLD_VERSION, issued="fictional-original")).encode()
            path.write_bytes(issued)
            original = path.parent / "fictional-other-original.json"
            original.write_bytes(b"FICTIONAL_ORIGINAL_MUST_REMAIN_UNCHANGED")
            target = path.parent / "grading-history" / (hashlib.sha256(issued).hexdigest() + ".json")
            target.parent.mkdir()
            target.symlink_to(original)
            with self.assertRaisesRegex(ValueError, "history checksum mismatch"):
                build.dump(path, {"grading_version": EXPECTED_VERSION})
            self.assertTrue(target.is_symlink())
            self.assertEqual(path.read_bytes(), issued)
            self.assertEqual(original.read_bytes(), b"FICTIONAL_ORIGINAL_MUST_REMAIN_UNCHANGED")
            self.assertEqual(list(target.parent.iterdir()), [target])


if __name__ == "__main__":
    unittest.main()
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise AssertionError("Patch preimage is not unique: " + old[:100])
    return text.replace(old, new, 1)


BOUND = '''def _bound_stats(archive, player, entry, *, game_id=None):
    """Reject recorded identity contradictions without inventing legacy evidence."""
    gid = player.get("game_id")
    if game_id is not None and game_id != gid:
        return None
    matches = [game for game in archive.get("games", []) if game.get("id") == gid]
    if archive.get("games") and len(matches) != 1:
        return None
    game = matches[0] if matches else {}
    team, opponent = player.get("team"), player.get("opp")
    home, away = game.get("home"), game.get("away")
    if home is not None and away is not None:
        if team not in (home, away) or home == away:
            return None
        expected = away if team == home else home
        if opponent is not None and opponent != expected:
            return None
        opponent = expected
    if not isinstance(entry, dict):
        return entry
    if (entry.get("team") is not None and team is not None and entry["team"] != team
            or entry.get("opp") is not None and opponent is not None and entry["opp"] != opponent):
        return None
    stats = entry.get("stats")
    if isinstance(stats, dict) and "_presence" in stats:
        metadata = stats["_presence"]
        if not isinstance(metadata, dict):
            return None
        original, context = metadata.get("original_row"), metadata.get("source_context")
        if (metadata.get("version") != getattr(scoring, "PRESENCE_VERSION", None) or metadata.get("kind") != "actual"
                or not isinstance(original, dict) or not isinstance(context, dict)
                or original.get("player_id") != player["id"]
                or original.get("team") != team or original.get("opponent") != opponent
                or (context.get("season"), context.get("week")) != (archive["season"], archive["week"])
                or original.get("stats") != {key: value for key, value in stats.items() if key != "_presence"}):
            return None
    return entry


'''


FINAL = '''def confirmed_final(game):
    """A post flag alone also covers cancellations; require a completed past game."""
    if game.get("state") != "post" or game.get("completed") is not True:
        return False
    try:
        kickoff = datetime.fromisoformat(game["kickoff"].replace("Z", "+00:00"))
        return kickoff.tzinfo is not None and kickoff < now_utc()
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


'''


def proposed(name, source, modern):
    if name == "01-retain-field-goals":
        path = "pull/scoring.py"
        new = replace_once(source[path], '"pts_allow", "yds_allow", "tm_off_snp", "fgm_50p"}',
                           '"pts_allow", "yds_allow", "tm_off_snp", "fgm_50p", "fgm"}')
    elif name == "02-bind-classic-statistics":
        path = "pull/grade.py"
        new = replace_once(source[path], 'def _prop_result(prop, direction, entry):', BOUND + 'def _prop_result(prop, direction, entry):')
        old_version = "statistical-presence-v3" if modern else "statistical-v2"
        version = "statistical-presence-v3-identity-20261025" if modern else "statistical-v3-identity-20261025"
        new = replace_once(new, 'GRADING_VERSION = "' + old_version + '"', 'GRADING_VERSION = "' + version + '"')
        new = replace_once(new, 'import json\n', 'import json\nimport hashlib\nimport os\nimport tempfile\nfrom pathlib import Path\n')
        new = replace_once(new, 'def _prop_result(prop, direction, entry):', ISSUED + 'def _prop_result(prop, direction, entry):')
        new = replace_once(new, 'value, outcome = _prop_result(p, side, stats.get(p["player_id"]))',
                           'value, outcome = _prop_result(p, side, _bound_stats(archive, who, stats.get(p["player_id"]), game_id=p["game_id"]))')
        new = replace_once(new, 'entry = stats.get(p["id"])', 'entry = _bound_stats(archive, p, stats.get(p["id"]))')
    elif name == "03-require-completed-finals":
        path = "pull/build.py"
        new = replace_once(source[path], '"state": status["state"],  # pre, in, post',
                           '"state": status["state"],  # pre, in, post\n            "completed": status.get("completed"),')
        new = replace_once(new, 'def load_games(season, week):', FINAL + 'def load_games(season, week):')
        # Both current-week final IDs and older-week score lookup must use it;
        # the past-week closing-lines list also must exclude cancelled games.
        if new.count('if g["state"] == "post"') != 3:
            raise AssertionError("Unexpected final-state call sites")
        new = new.replace('if g["state"] == "post"', 'if confirmed_final(g)')
    elif name == "04-reject-negative-count-expectations" and modern:
        path = "pull/scoring.py"
        old = '''        if not projection and ((key in ACTUAL_COUNTS and value < 0)
                               or key in ACTUAL_COUNTS | {"pass_yd", "rush_yd", "rec_yd"} and int(value) != value):'''
        replacement = '''        if ((key in ACTUAL_COUNTS and value < 0)
                or not projection and key in ACTUAL_COUNTS | {"pass_yd", "rush_yd", "rec_yd"} and int(value) != value):'''
        new = replace_once(source[path], old, replacement)
    elif name == "05-half-ppr-missing-labels":
        path = "output/app.js"
        new = replace_once(source[path], 'p.proj_half ?? p.proj_ppr', 'Number.isFinite(p.proj_half) ? p.proj_half : null')
        # Parenthesize the inner conditional to preserve the outer half/full choice.
        new = replace_once(new,
            'return S.sc.half ? Number.isFinite(p.proj_half) ? p.proj_half : null : p.proj_ppr;',
            'return S.sc.half ? (Number.isFinite(p.proj_half) ? p.proj_half : null) : p.proj_ppr;')
        new = replace_once(new, 'p.avg_half ?? p.avg_ppr', '(Number.isFinite(p.avg_half) ? p.avg_half : null)')
        old = '  if (isDefault()) return prop.adj_h == null ? prop : { ...prop, line: prop.line_h, adj: prop.adj_h, proj: prop.proj_h, over: prop.over_h, values: prop.values.map((x) => ({ ...x, v: x.h ?? x.v })) };'
        half = '''  if (isDefault()) {
    const values = prop.values.filter(x => Number.isFinite(x.h)).map(x => ({ ...x, v: x.h }));
    const missing = !Number.isFinite(prop.adj_h) || !Number.isFinite(prop.line_h);
    return { ...prop, line: missing ? null : prop.line_h, adj: missing ? null : prop.adj_h,
      proj: Number.isFinite(prop.proj_h) ? prop.proj_h : null, lean: missing ? null : prop.lean,
      over: missing ? 0 : values.filter(x => x.v > prop.line_h).length, n: values.length, values,
      scoring_missing: missing };
  }'''
        new = replace_once(new, old, half)
        for function, markup in (
            ("propChip", '<span class="pchip"><span>FPts</span><span class="muted">Half PPR unavailable</span></span>'),
            ("catCard", '<div class="card"><h3>Fantasy Points · Half PPR</h3><p class="muted">Half PPR projection and line unavailable.</p></div>')):
            old = 'function ' + function + '(p, raw) {\n  const prop = pv(p, raw);'
            replacement = old + '\n  if (prop.scoring_missing) return `' + markup + '`;'
            new = replace_once(new, old, replacement)
    else:
        raise AssertionError(name)
    if name == "02-bind-classic-statistics":
        builder = replace_once(source["pull/build.py"], 'def dump(path, data):\n',
                               'def dump(path, data):\n    if path.name == "track_record.json":\n        grade.preserve_issued_record(path)\n')
        return {path: new, "pull/build.py": builder,
                "tests/test_grading_identity_v3.py": REGRESSIONS.replace("__VERSION__", version).replace("__OLD_VERSION__", old_version)}
    return {path: new}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-current-suite", action="store_true")
    args = parser.parse_args()
    patch_dir = AUDIT / "patches"
    patch_dir.mkdir(exist_ok=True)
    manifest = {"schema_version": "website-math-patch-qualification-v2",
                "scope": "FICTIONAL_PATCH_VALIDATION_ONLY_NOT_RELEASE_QUALIFICATION", "baselines": {}}
    for baseline in ("website-audit", "website-phase2"):
        root = AUDIT / baseline
        modern = baseline == "website-phase2"
        source = {p: (root / p).read_text() for p in ("pull/scoring.py", "pull/grade.py", "pull/build.py", "output/app.js")}
        names = ["01-retain-field-goals", "02-bind-classic-statistics", "03-require-completed-finals"]
        if modern:
            names.append("04-reject-negative-count-expectations")
        names.append("05-half-ppr-missing-labels")
        patches = []
        # Each focused patch is generated independently against the exact pin.
        for name in names:
            changes = proposed(name, source, modern)
            body = "".join("".join(difflib.unified_diff(source.get(path, "").splitlines(keepends=True), new.splitlines(keepends=True),
                                               fromfile="a/" + path if path in source else "/dev/null", tofile="b/" + path))
                           for path, new in changes.items())
            target = patch_dir / (baseline + "-math-" + name + ".patch")
            target.write_text(body)
            patches.append({"path": str(target.relative_to(AUDIT)), "sha256": hashlib.sha256(body.encode()).hexdigest(),
                            "preimages": {path: hashlib.sha256(source[path].encode()).hexdigest() if path in source else None for path in changes},
                            "depends_on": ["02-bind-classic-statistics"] if name == "03-require-completed-finals" else []})
        with tempfile.TemporaryDirectory(prefix="website-math-patches-") as temporary:
            copy = Path(temporary)
            # Full plain copies include tests, config, workflow and public files;
            # no shared .git, worktree registration, or original writable paths.
            shutil.copytree(root, copy, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"))
            for item in patches:
                command = ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(AUDIT / item["path"])]
                applied = subprocess.run(command, cwd=copy, text=True, capture_output=True)
                if applied.returncode:
                    raise RuntimeError(applied.stdout + applied.stderr)
            for path in source:
                if path.endswith(".py"):
                    compile((copy / path).read_text(), path, "exec")
            syntax = subprocess.run(["node", "--check", str(copy / "output/app.js")], text=True, capture_output=True)
            if syntax.returncode:
                raise RuntimeError(syntax.stderr)
            command = [sys.executable, "-B", str(AUDIT / "website_math_repro.py"), "--root", str(copy), "--expect-patches"]
            checked = subprocess.run(command, text=True, capture_output=True)
            if checked.returncode:
                raise RuntimeError(checked.stdout + checked.stderr)
            details = json.loads(checked.stdout)
            # Avoid ephemeral paths in the retained public-safe result.
            details["root"] = "DISPOSABLE_FICTIONAL_SOURCE_COPY"
            manifest["baselines"][baseline] = {"patches": patches, "repro": details}
            manifest["baselines"][baseline]["patched_source_sha256"] = {
                path: hashlib.sha256((copy / path).read_bytes()).hexdigest()
                for path in list(source) + ["tests/test_grading_identity_v3.py"]}
            manifest["baselines"][baseline]["source_pin"] = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
            label = subprocess.run(["node", str(AUDIT / "website_ppr_label_repro.cjs"), "--root", str(copy), "--expect-patches"],
                                   text=True, capture_output=True)
            if label.returncode:
                raise RuntimeError(label.stdout + label.stderr)
            manifest["baselines"][baseline]["half_ppr_scratch"] = json.loads(label.stdout)
            if modern:
                program = '''import sys,unittest,json
sys.path.insert(0,sys.argv[1])
from website_math_repro import install_network_guard
install_network_guard()
sys.path[:0]=["pull","tools","tests"]
suite=unittest.defaultTestLoader.discover("tests",pattern="test_grading_identity_v3.py")
result=unittest.TextTestRunner().run(suite)
print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))))
sys.exit(not result.wasSuccessful())
'''
                migration = subprocess.run([sys.executable, "-B", "-c", program, str(AUDIT)], cwd=copy, text=True, capture_output=True)
                if migration.returncode:
                    raise RuntimeError(migration.stdout + migration.stderr)
                manifest["baselines"][baseline]["migration_regressions"] = json.loads(migration.stdout)
            if args.full_current_suite and not modern:
                program = '''import sys,json,unittest,socket,requests
from pathlib import Path
def blocked(*a,**k): raise AssertionError("NETWORK_DISABLED_FULL_FICTIONAL_SUITE")
requests.sessions.Session.request=blocked
socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked
sys.path[:0]=[str(Path.cwd()/"pull"),str(Path.cwd()/"tools"),str(Path.cwd()/"tests")]
all_suite=unittest.defaultTestLoader.discover("tests")
def flat(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite): yield from flat(item)
  else: yield item
original=[];added=[]
for case in flat(all_suite):
 (added if case.id().startswith("test_grading_identity_v3.") else original).append(case)
assert len(original)==97,("original suite count",len(original))
assert len(added)==9,("new regression count",len(added))
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(original+added))
print(json.dumps(dict(original_tests=len(original),new_tests=len(added),total=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),network="DISABLED",grading_version=__import__("grade").GRADING_VERSION)))
sys.exit(not result.wasSuccessful())
'''
                python = AUDIT / "venv/bin/python"
                if not python.exists():
                    python = Path(sys.executable)
                checked = subprocess.run([str(python), "-B", "-c", program], cwd=copy, text=True, capture_output=True)
                log = AUDIT / "website-math-full-current-suite.log"
                log.write_text(checked.stderr.replace(str(copy), "DISPOSABLE_FULL_SOURCE_COPY"))
                if checked.returncode:
                    raise RuntimeError(checked.stdout + checked.stderr)
                summary = json.loads(checked.stdout.strip().splitlines()[-1])
                summary["log_path"] = log.relative_to(AUDIT).as_posix()
                summary["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
                manifest["baselines"][baseline]["full_current_suite"] = summary
                (AUDIT / "website-math-full-current-suite.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    output = AUDIT / "website-math-patch-validation.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for baseline, details in manifest["baselines"].items():
        print(baseline, len(details["patches"]), "focused patches;", details["repro"]["checks"], "checks passed")


if __name__ == "__main__":
    main()
