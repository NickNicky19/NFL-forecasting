"""Fixed metadata-only block until the existing lab route is handed over.

This is intentionally not an activation API. Source/publication policy cannot
be bypassed with a flag, repository permission or fabricated readiness file.
The scheduler still runs this guard; no recorder is replaced or retired here.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re

REPOSITORY="NickNicky19/NFL-forecasting"
MAX_RECEIPT_BYTES=8192
EXIT_BLOCKED=78


def readiness(root,*,repository,source_commit,run_id,run_attempt,observed_at=None):
    root=Path(root)
    reasons=["QUALIFIED_HOSTED_HANDOVER_NOT_ACCEPTED","PRIVATE_DURABILITY_NOT_VERIFIED"]
    if repository!=REPOSITORY:reasons.append("UNEXPECTED_REPOSITORY")
    if not (root/"config/operational-source-policy-v2.json").is_file():
        reasons.append("PERMITTED_SOURCE_POLICY_FILE_ABSENT")
    if not (root/"config/operational-publication-review-v2.json").is_file():
        reasons.append("EXACT_PUBLICATION_REVIEW_ABSENT")
    # Existence is diagnostic only. Even both files present cannot bypass the
    # fixed block or establish private access, byte review or actual readiness.
    return dict(schema_version="lab-hosted-safety-readiness-v1",state="BLOCKED_PENDING_QUALIFIED_HANDOVER",
        repository=REPOSITORY if repository==REPOSITORY else "UNEXPECTED_REPOSITORY",
        source_commit=source_commit if isinstance(source_commit,str) and re.fullmatch(r"[0-9a-f]{40}",source_commit) else None,
        run_id=run_id if isinstance(run_id,str) and run_id.isascii() and run_id.isdecimal() else None,
        run_attempt=run_attempt if isinstance(run_attempt,str) and run_attempt.isascii() and run_attempt.isdecimal() else None,
        observed_at=(observed_at or datetime.now(timezone.utc)).isoformat(),reasons=reasons,
        acquisition_started=False,capture_started=False,new_fits_predictions=0,
        state_publication_started=False,scientific_confirmation="NO_NEW_EVIDENCE",
        scheduler="EXISTING_CRON_AND_SINGLE_WRITER_RETAINED",exit_code=EXIT_BLOCKED)


def save_receipt(path,document):
    body=(json.dumps(document,sort_keys=True,indent=2)+"\n").encode()
    if len(body)>MAX_RECEIPT_BYTES:raise ValueError("readiness metadata exceeds fixed bound")
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError("readiness receipt path cannot use links")
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,"wb") as output:output.write(body);output.flush();os.fsync(output.fileno())
    except BaseException:
        # A failed bounded receipt is retained; never truncate it for a retry.
        raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,default=Path.cwd())
    parser.add_argument("--receipt",type=Path,required=True)
    args=parser.parse_args()
    result=readiness(args.root,repository=os.environ.get("GITHUB_REPOSITORY",""),
        source_commit=os.environ.get("GITHUB_SHA",""),run_id=os.environ.get("GITHUB_RUN_ID",""),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT",""))
    save_receipt(args.receipt,result)
    print(json.dumps(result,sort_keys=True))
    return EXIT_BLOCKED


if __name__=="__main__":raise SystemExit(main())
