"""New stdlib mocked-HTTP canary checks. No network, releases or NFL inputs."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError

SOURCE = Path(__file__).resolve().parents[1] / "tools/private_storage_probe.py"
SPEC = importlib.util.spec_from_file_location("private_storage_probe", SOURCE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
TOKEN = "ghs_fictional_automatic_job_token"


class Response:
    def __init__(self, status=200, body=b"", headers=None):
        self.status, self.body, self.headers = status, body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.body[:limit]


def reply(body, status=200, headers=None):
    return Response(status, json.dumps(body).encode(), headers)


class MockHTTP:
    def __init__(self, answers):
        self.answers, self.requests = list(answers), []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if not self.answers:
            raise AssertionError("Unplanned HTTP request")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class StorageProbeChecks(unittest.TestCase):
    def client(self, answers=(), **kwargs):
        transport = MockHTTP(answers)
        return probe.Client(TOKEN, "123", transport=transport, **kwargs), transport

    def draft(self, client, assets=(), **changes):
        result = {"id": 11, "draft": True, "published_at": None, "tag_name": client.tag,
            "url": client.path("/releases/11"), "assets": [] if assets == () else assets,
            "upload_url": "https://uploads.github.com/repos/" + probe.REPOSITORY + "/releases/11/assets{?name,label}"}
        result.update(changes)
        return result

    def asset(self, client, **changes):
        result = {"id": 22, "name": probe.FIXTURE_NAME, "url": client.path("/releases/assets/22"),
            "browser_download_url": client.browser(), "size": len(probe.fixture("123")), "state": "uploaded",
            "digest": "sha256:" + hashlib.sha256(probe.fixture("123")).hexdigest()}
        result.update(changes)
        return result

    def controls(self):
        data = b"a" * 64 + b"  gh_2.0.0_linux_amd64.tar.gz\n"
        asset = {"id": 33, "name": probe.CONTROL_NAME, "size": len(data), "state": "uploaded",
            "url": probe.API + "/repos/cli/cli/releases/assets/33",
            "browser_download_url": "https://github.com/cli/cli/releases/download/v2.0.0/" + probe.CONTROL_NAME}
        release = {"id": 44, "draft": False, "published_at": "2021-08-24T00:00:00Z", "assets": [asset],
            "tag_name": probe.CONTROL_TAG, "url": probe.API + "/repos/cli/cli/releases/44"}
        return [reply({"full_name": probe.REPOSITORY, "url": probe.API + "/repos/" + probe.REPOSITORY, "private": False}), reply(release), reply(asset),
            Response(302, headers={"Location": "https://release-assets.githubusercontent.com/public?secret=never_log"}),
            Response(200, data), Response(302, headers={"Location": "https://objects.githubusercontent.com/public?signature=never_log"}), Response(200, data)]

    def assert_state(self, state, function, *args):
        with self.assertRaises(probe.ProbeError) as context:
            function(*args)
        self.assertEqual(context.exception.state, state)
        self.assertNotIn(TOKEN, str(context.exception))

    def test_write_creates_one_draft_one_small_asset_without_overwrite(self):
        client, http = self.client()
        asset, draft = self.asset(client), self.draft(client)
        http.answers = [reply({"full_name": probe.REPOSITORY}), Response(404), reply(draft, 201), reply(draft),
            reply(asset, 201), reply(self.draft(client, [asset]))]
        state, checks = probe.write(client)
        self.assertEqual(state, "WRITE_CANARY_CREATED")
        self.assertTrue(checks["draft_unpublished"])
        posts = [item for item, _ in http.requests if item.method == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[1].data, probe.fixture("123"))
        self.assertLessEqual(len(posts[1].data), 1024)
        self.assertEqual(json.loads(posts[0].data)["draft"], True)
        self.assert_state("PROBE_GUARD_STOP", client.request, client.path("/releases"))
        self.assertEqual(client.calls, 6)
        for published, failed_upload in ((True, False), (False, True)):
            client, http = self.client()
            http.answers = [reply({"full_name": probe.REPOSITORY}), Response(404), reply(self.draft(client), 201),
                reply(self.draft(client, published_at="changed" if published else None))]
            if failed_upload:
                http.answers.append(URLError("ambiguous upload failure"))
            with self.assertRaises(probe.ProbeError):
                probe.write(client)
            self.assertEqual(sum(request.method == "POST" for request, _ in http.requests), 2 if failed_upload else 1)

    def test_read_needs_ten_404s_and_positive_public_controls(self):
        client, http = self.client(self.controls() + [Response(404)] * 10, release_id=11, asset_id=22)
        state, checks = probe.read(client)
        self.assertEqual(state, "READ_BOUNDARY_DENIED")
        self.assertEqual(sum(name.endswith("_404") for name in checks), 10)
        self.assertTrue(all(checks.values()))
        self.assertEqual(client.calls, 17)
        self.assertIn("anonymous_browser_after_read_only_api_404", checks)
        self.assertIn("anonymous_browser_after_anonymous_api_404", checks)
        self.assertNotIn("read_only_browser_404", checks)
        self.assertIsNotNone(http.requests[0][0].get_header("Authorization"))
        self.assertEqual(http.requests[0][0].full_url, client.path(""))
        self.assertTrue(all(request.get_header("Authorization") is None for request, _ in http.requests[1:7]))
        for request, timeout in http.requests:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 20)
            if request.host != "api.github.com":
                self.assertIsNone(request.get_header("Authorization"))
        private = http.requests[-10:]
        self.assertIsNotNone(private[0][0].get_header("Authorization"))
        self.assertIsNone(private[4][0].get_header("Authorization"))
        self.assertTrue(all(request.get_header("Authorization") is None for request, _ in private[5:]))

    def test_read_visibility_is_failure_including_empty_list_and_redirect(self):
        for index in range(10):
            for visible in (Response(200, b"[]"), Response(302, headers={"Location": "https://release-assets.githubusercontent.com/private?secret=x"})):
                with self.subTest(index=index, status=visible.status):
                    client, http = self.client(self.controls() + [Response(404)] * index + [visible], release_id=11, asset_id=22)
                    self.assert_state("FAIL_PRIVATE_BOUNDARY", probe.read, client)
                    self.assertEqual(client.calls, 8 + index)

    def test_403_rate_limit_auth_and_transport_errors_never_prove_privacy(self):
        for result in (Response(403), Response(401), Response(429), Response(500),
                Response(404, headers={"X-RateLimit-Remaining": "0"}), Response(404, headers={"Retry-After": "1"})):
            self.assert_state("INCONCLUSIVE_DENIAL", probe.denial, (result.status,
                {key.lower(): value for key, value in result.headers.items()}, result.body))
        client, _ = self.client([URLError("https://secret-token.invalid/never_log")])
        self.assert_state("PROBE_GUARD_STOP", client.request, client.path(""))
        client, _ = self.client([Response(403, b"private error body " + TOKEN.encode())], release_id=11, asset_id=22)
        self.assert_state("PROBE_GUARD_STOP", probe.read, client)

    def test_broken_public_controls_or_mismatched_download_cannot_pass(self):
        for index in range(7):
            answers = self.controls()
            answers[index] = Response(404)
            client, _ = self.client(answers, release_id=11, asset_id=22)
            with self.subTest(index=index), self.assertRaises(probe.ProbeError):
                probe.read(client)
        answers = self.controls()
        answers[-1] = Response(200, b"b" * len(answers[-1].body))
        client, _ = self.client(answers, release_id=11, asset_id=22)
        self.assert_state("PUBLIC_CONTROL_FAILED", probe.read, client)

    def test_restore_fresh_writer_checks_draft_and_exact_authenticated_bytes(self):
        client, http = self.client(release_id=11, asset_id=22)
        asset = self.asset(client)
        pair = [reply(self.draft(client, [asset])), reply(asset),
            Response(302, headers={"Location": "https://release-assets.githubusercontent.com/canary?signature=never_log"}),
            Response(200, probe.fixture("123")), reply(self.draft(client, [asset]))]
        http.answers = pair
        state, checks = probe.restore(client)
        self.assertEqual(state, "RESTORE_EXACT_BODY_VERIFIED")
        self.assertTrue(all(checks.values()))
        self.assertEqual(client.calls, 5)
        self.assertTrue(checks["post_download_draft_single_asset"])
        for request, _ in http.requests:
            if request.host != "api.github.com":
                self.assertIsNone(request.get_header("Authorization"))
        client, http = self.client(release_id=11, asset_id=22)
        http.answers = [reply(self.draft(client, [self.asset(client)])), reply(self.asset(client)), Response(200, b"wrong")]
        self.assert_state("RESTORE_MISMATCH", probe.restore, client)
        client, http = self.client(release_id=11, asset_id=22)
        http.answers = [reply(self.draft(client, [self.asset(client)], published_at="changed"))]
        self.assert_state("DRAFT_IDENTITY_REQUIRED", probe.restore, client)

    def test_post_download_draft_or_asset_mutation_cannot_pass(self):
        prototype, _ = self.client(release_id=11, asset_id=22)
        for changes, state in (({"draft": False}, "DRAFT_IDENTITY_REQUIRED"),
                ({"published_at": "changed"}, "DRAFT_IDENTITY_REQUIRED"),
                ({"id": 12}, "DRAFT_IDENTITY_REQUIRED"), ({"assets": []}, "ASSET_IDENTITY_REQUIRED"),
                ({"assets": [self.asset(prototype, id=23)]}, "ASSET_IDENTITY_REQUIRED")):
            client, http = self.client(release_id=11, asset_id=22)
            asset = self.asset(client)
            changed = self.draft(client, [asset])
            changed.update(changes)
            http.answers = [reply(self.draft(client, [asset])), reply(asset), Response(200, probe.fixture("123")),
                reply(changed)]
            with self.subTest(changes=changes):
                self.assert_state(state, probe.restore, client)
                self.assertEqual(client.calls, 4)

    def test_authenticated_control_is_own_repo_and_other_controls_are_anonymous(self):
        client, http = self.client(self.controls(), release_id=11, asset_id=22)
        probe.public_controls(client)
        self.assertEqual(http.requests[0][0].full_url, client.path(""))
        self.assertIsNotNone(http.requests[0][0].get_header("Authorization"))
        self.assertTrue(all(request.get_header("Authorization") is None for request, _ in http.requests[1:]))
        client, http = self.client()
        external = probe.API + "/repos/cli/cli/releases/tags/" + probe.CONTROL_TAG
        self.assert_state("PROBE_GUARD_STOP", client.request, external)
        self.assertFalse(http.requests)
        for own in ({"full_name": "other/repo", "url": client.path("")},
                {"full_name": probe.REPOSITORY, "url": probe.API + "/repos/other/repo"},
                {"full_name": probe.REPOSITORY, "url": client.path(""), "private": True}):
            client, _ = self.client([reply(own)], release_id=11, asset_id=22)
            self.assert_state("PUBLIC_CONTROL_FAILED", probe.public_controls, client)

    def test_draft_repo_release_asset_and_body_identity_are_mandatory(self):
        client, _ = self.client(release_id=11, asset_id=22)
        for changes in ({"draft": False}, {"published_at": "now"}, {"tag_name": "other"},
                {"url": probe.API + "/repos/other/repo/releases/11"}, {"id": 12}, {"assets": None}):
            with self.subTest(changes=changes):
                self.assert_state("DRAFT_IDENTITY_REQUIRED", probe.pin_draft, client, self.draft(client, **changes))
        for changes in ({"name": "private.csv"}, {"id": 23}, {"size": 999}, {"digest": "sha256:wrong"},
                {"browser_download_url": "https://evil.invalid/"}, {"state": "starter"}):
            with self.subTest(changes=changes):
                self.assert_state("ASSET_IDENTITY_REQUIRED", probe.pin_asset, client, self.asset(client, **changes))
        self.assert_state("ASSET_IDENTITY_REQUIRED", probe.pin_single_asset, client,
            self.draft(client, [self.asset(client), self.asset(client)]))

    def test_url_methods_redirects_and_auth_are_strict(self):
        client, http = self.client([Response(302, headers={"Location": "https://evil.invalid/?token=never_log"})], release_id=11, asset_id=22)
        for url in ("http://api.github.com/repos/" + probe.REPOSITORY, "https://api.github.com.evil.invalid/",
                "https://user@api.github.com/", "https://api.github.com:443/repos/" + probe.REPOSITORY,
                client.path("/releases/12"), client.browser() + "?extra=1", "https://uploads.github.com/other"):
            with self.subTest(url=url), self.assertRaises(probe.ProbeError):
                client.request(url)
        for method in ("DELETE", "PATCH", "PUT"):
            with self.assertRaises(probe.ProbeError):
                client.request(client.path("/releases/11"), method=method)
        with self.assertRaises(probe.ProbeError):
            client.request(client.path("/releases/assets/22"), download=True)
        self.assertEqual(client.calls, 1)
        self.assertIsNone(probe.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))

    def test_ambiguous_post_is_consumed_never_retried_or_redirected(self):
        client, http = self.client([URLError("ambiguous POST failure")])
        for _ in range(2):
            with self.assertRaises(probe.ProbeError):
                client.request(client.path("/releases"), method="POST", data=b"{}")
        self.assertEqual(len(http.requests), 1)
        client, http = self.client([Response(307, headers={"Location": "https://uploads.github.com/elsewhere"})])
        result = client.request(client.path("/releases"), method="POST", data=b"{}")
        self.assertEqual(result[0], 307)
        self.assertEqual(len(http.requests), 1)

    def test_request_count_transfer_time_and_redirect_budgets_are_finite(self):
        with patch.object(probe.signal, "getitimer", return_value=(100., 0.)), \
                patch.object(probe.signal, "getsignal", return_value=probe.signal.SIG_DFL), \
                patch.object(probe.signal, "setitimer") as timer, \
                patch.object(probe.time, "monotonic", side_effect=[10., 13.]):
            with probe.request_deadline(True):
                pass
            self.assertEqual([item.args for item in timer.call_args_list],
                [(probe.signal.ITIMER_REAL, 20.), (probe.signal.ITIMER_REAL, 0), (probe.signal.ITIMER_REAL, 97.)])
        client, http = self.client([Response(404)] * 20)
        for _ in range(20):
            client.request(client.path(""))
        self.assert_state("PROBE_GUARD_STOP", client.request, client.path(""))
        self.assertEqual(len(http.requests), 20)
        for body, headers in ((b"x" * (probe.MAX_RESPONSE + 1), {}), (b"", {"Content-Length": str(probe.MAX_TRANSFER + 1)})):
            client, _ = self.client([Response(200, body, headers)])
            self.assert_state("PROBE_GUARD_STOP", client.request, client.path(""))
        client, _ = self.client()
        client.transferred = probe.MAX_TRANSFER
        self.assert_state("PROBE_GUARD_STOP", client.request, client.path(""))
        client, _ = self.client()
        client.started -= 121
        self.assert_state("PROBE_GUARD_STOP", client.request, client.path(""))
        client, http = self.client([Response(302, headers={"Location": "https://objects.githubusercontent.com/x"})] * 3, release_id=11, asset_id=22)
        with self.assertRaises(probe.ProbeError):
            client.request(client.browser(), download=True)
        self.assertEqual(len(http.requests), 3)

    def test_cli_scope_token_attempt_and_hash_guards_and_safe_error_summary(self):
        base = {"GITHUB_REPOSITORY": probe.REPOSITORY, "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "123", "GITHUB_TOKEN": TOKEN, "PROBE_PERMISSION": "read"}
        args = ["read", "--release-id", "11", "--asset-id", "22", "--expected-sha256", hashlib.sha256(probe.fixture("123")).hexdigest()]
        for changes in ({"GITHUB_REPOSITORY": "other/repo"}, {"GITHUB_RUN_ATTEMPT": "2"}, {"GITHUB_TOKEN": "ghp_not_automatic"},
                {"PROBE_PERMISSION": "write"}, {"GITHUB_EVENT_NAME": "schedule"}, {"GITHUB_ACTIONS": "false"}):
            with self.subTest(changes=changes), patch.object(probe, "limits"), patch("sys.stdout", new_callable=io.StringIO) as output:
                http = MockHTTP([])
                self.assertEqual(probe.main(args, environ={**base, **changes}, transport=http), 1)
                self.assertFalse(http.requests)
                self.assertNotIn(TOKEN, output.getvalue())
        http = MockHTTP([URLError("https://secret.invalid/?token=" + TOKEN)])
        with patch.object(probe, "limits"), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(probe.main(args, environ=base, transport=http), 1)
            result = json.loads(output.getvalue())
            self.assertFalse(result["private_durability_qualified"])
            self.assertNotIn(TOKEN, output.getvalue())
            self.assertNotIn("secret.invalid", output.getvalue())
            self.assertLess(len(output.getvalue()), probe.MAX_SUMMARY)
        with patch.object(probe, "limits"), patch("sys.stdout", new_callable=io.StringIO):
            http = MockHTTP([])
            self.assertEqual(probe.main(args[:-1] + ["wrong-hash"], environ=base, transport=http), 1)
            self.assertFalse(http.requests)

    def test_workflow_reuses_one_scheduler_and_preserves_entire_lab_job(self):
        workflow = (SOURCE.parents[1] / ".github/workflows/lab.yml").read_text()
        self.assertEqual(workflow.count("- cron:"), 1)
        self.assertEqual(workflow.count("group: nfl-lab-single-writer"), 1)
        self.assertIn("if: github.event_name != 'workflow_dispatch' || inputs.mode != 'storage-probe'", workflow)
        lab = "  lab:\n" + workflow.split("  lab:\n", 1)[1].split("  storage-probe-write:\n", 1)[0]
        lab = lab.replace("    if: github.event_name != 'workflow_dispatch' || inputs.mode != 'storage-probe'\n", "", 1)
        self.assertEqual(hashlib.sha256(lab.encode()).hexdigest(),
            "8f9eb212533ecb5dba0efa0144db19e63ead6726912e5475dfd5ac742b5e50a3")
        self.assertEqual(workflow.count("timeout-minutes: 3\n"), 3)
        self.assertEqual(workflow.count("GITHUB_TOKEN: ${{ github.token }}"), 3)
        self.assertIn("needs: [storage-probe-write, storage-probe-read]", workflow)
        probe_jobs = workflow.split("  storage-probe-write:", 1)[1]
        self.assertNotIn("upload-artifact", probe_jobs)
        self.assertNotIn("secrets.", probe_jobs)
        self.assertNotIn("pip install", probe_jobs)


if __name__ == "__main__":
    unittest.main()
