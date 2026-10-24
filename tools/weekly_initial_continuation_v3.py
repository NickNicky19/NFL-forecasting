"""New actual inference clocks from an explicitly registered original checkpoint."""


def backend(plan,*,clock,resource_check):
    from nfl_lab.weekly_initial_continuation_v3 import InitialContinuationBackend
    return InitialContinuationBackend(plan,clock=clock,resource_check=resource_check)


def validate(plan,*,now):
    from nfl_lab.weekly_initial_continuation_v3 import validate_plan
    return validate_plan(plan,now=now)


def main():
    from tools.weekly_generic_future_producer import main as shared
    return shared(backend_factory=backend,plan_validator=validate,diagnostics=True)


if __name__=="__main__":
    from pathlib import Path
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
