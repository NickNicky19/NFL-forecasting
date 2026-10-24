"""Closed opt-in identities for the original bootstrap and one new recovery."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InitialHorizon:
    version: int
    cutoff: str
    registration_path: str
    build_config_path: str
    checkpoint_config_path: str
    builder_config_path: str
    public_config_path: str
    build_registration_schema: str
    build_registration_id: str
    builder_version: str
    builder_scope: str
    public_version: str

    def adapter(self):
        if self.version == 1:
            from . import weekly_initial_remaining_v1 as initial
        elif self.version == 2:
            from . import weekly_initial_remaining_v2 as initial
        else:
            from . import weekly_initial_continuation_v3 as initial
        return initial


ORIGINAL = InitialHorizon(1, "2026-10-24T15:00:00Z", "config/weekly-initial-remaining-v1-registration.json",
    "config/genuine-hosted-fixed-build-v1.json", "config/gha-private-checkpoint-v1.json",
    "config/hosted-initial-plan-builder-v1.json", "config/hosted-public-release-plan-v1.json",
    "genuine-hosted-fixed-build-registration-v1", "initial-remaining-2026W7-new15Z-operational-build-v1",
    "weekly-hosted-initial-plan-builder-v1", "STRICT18_INITIAL15Z_METADATA_PLAN_ONLY", "weekly-hosted-public-release-plan-v1")
RECOVERY = InitialHorizon(2, "2026-10-25T00:00:00Z", "config/weekly-initial-remaining-v2-registration.json",
    "config/genuine-hosted-fixed-build-v2.json", "config/gha-private-checkpoint-v2.json",
    "config/hosted-initial-plan-builder-v2.json", "config/hosted-public-release-plan-v2.json",
    "genuine-hosted-fixed-build-registration-v2", "initial-remaining-2026W7-20261025T00Z-operational-build-v2",
    "weekly-hosted-initial-plan-builder-v2", "STRICT18_INITIAL_RECOVERY00Z_METADATA_PLAN_ONLY", "weekly-hosted-public-release-plan-v2")
CONTINUATION = InitialHorizon(3, "2026-10-25T00:00:00Z", "config/weekly-initial-continuation-v5-registration.json",
    "config/genuine-hosted-fixed-build-v2.json", "config/gha-private-checkpoint-v3.json",
    "config/hosted-initial-plan-builder-v3.json", "config/hosted-public-release-plan-v3.json",
    "genuine-hosted-fixed-build-registration-v2", "initial-remaining-2026W7-20261025T00Z-operational-build-v2",
    "weekly-hosted-initial-plan-builder-v3", "STRICT18_CONTINUATION00Z_ZERO_FIT_METADATA_PLAN_ONLY", "weekly-hosted-public-release-plan-v3")


def resolve(recovery_v2=False,*,continuation_v3=False):
    if type(recovery_v2) is not bool or type(continuation_v3) is not bool or (recovery_v2 and continuation_v3):
        raise ValueError("explicit boolean recovery opt-in required")
    if continuation_v3:return CONTINUATION
    return RECOVERY if recovery_v2 else ORIGINAL
