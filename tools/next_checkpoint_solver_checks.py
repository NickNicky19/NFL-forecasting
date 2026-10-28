"""One finite fictional-only verification of the new convex solver."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import resource
import time

import numpy as np
from scipy.optimize import minimize

from nfl_lab.next_checkpoint_lad import fit_lad, apply_lad, SolverFailure


def independent_qp(x, y, model):
    """Small dense epigraph QP; intentionally differs from the ADMM solver."""
    z = (x - model["center"]) / model["scale"]
    design = np.column_stack([np.ones(len(y)), z])
    coefficients = design.shape[1]
    alpha = model["physical_alpha"]
    def objective(v):
        gradient = np.r_[0., 2. * alpha * v[1:coefficients], np.ones(len(y))]
        return float(v[coefficients:].sum() + alpha * np.sum(v[1:coefficients] ** 2)), gradient
    matrix = np.vstack([np.column_stack([-design, np.eye(len(y))]), np.column_stack([design, np.eye(len(y))])])
    offset = np.r_[y, -y]
    initial_beta = np.r_[np.median(y), np.zeros(z.shape[1])]
    initial = np.r_[initial_beta, np.abs(y - design @ initial_beta)]
    fit = minimize(objective, initial, jac=True, method="SLSQP",
                   bounds=[(None, None)] + [(0., None)] * z.shape[1] + [(0., None)] * len(y),
                   constraints=[{"type": "ineq", "fun": lambda v: matrix @ v + offset, "jac": lambda v: matrix}],
                   options={"maxiter": 1000, "ftol": 1e-11})
    if not fit.success or np.min(matrix @ fit.x + offset) < -1e-7:
        raise AssertionError("independent fictional epigraph solver failed: " + fit.message)
    return float(fit.fun)


def main():
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    cases = [
        ("one_input_outlier", [[-2], [-1], [0], [1], [2], [3], [4]], [-4, -2, 0, 2, 4, 6, 100]),
        ("two_inputs_signed", [[-2, 1], [-1, 2], [0, -1], [1, 0], [2, 3], [3, -2], [4, 4]], [-10, -7, -8, -3, 1, -4, 8]),
        ("constant_input", [[5], [5], [5], [5], [5]], [-9, -2, -1, 0, 20]),
        ("negative_relation_constraint", [[0], [1], [2], [3], [4]], [8, 6, 4, 2, 0]),
        ("constant_output_floor", [[-2, 3], [-1, 2], [0, 1], [1, 0], [2, -1]], [-3, -3, -3, -3, -3]),
        ("two_inputs_inactive_slope", [[0, 0], [1, 0], [2, 1], [3, 0], [4, 2], [5, 3]], [0, 2, 3, 6, 6, 7]),
    ]
    records = []
    for name, x, y in cases:
        x, y = np.array(x, float), np.array(y, float)
        model = fit_lad(x, y)
        reference = independent_qp(x, y, model)
        candidate = model["certificate"]["physical_primal"]
        assert abs(candidate - reference) <= 2e-6 * (1. + abs(reference)), (name, candidate, reference)
        assert (model["coef"][1:] >= 0).all()
        assert np.isfinite(apply_lad(model, x)).all()
        expected_scale = max(1., 1.4826 * np.median(np.abs(y - np.median(y))))
        assert model["response_scale"] == expected_scale
        assert model["physical_alpha"] == 10. / expected_scale
        if name == "constant_input":
            assert model["coef"][1] == 0 and model["coef"][0] == -1
        if name == "negative_relation_constraint":
            assert model["coef"][1] == 0
        records.append({"name": name, "state": "PASS", "physical_primal": candidate, "independent_QP_objective": reference,
                        "iterations": model["certificate"]["iterations"], "gap": model["certificate"]["physical_gap"]})
    try:
        fit_lad(np.arange(7.)[:, None], np.array([0., 2., 3., 6., 8., 9., 100.]), max_iter=1)
    except SolverFailure:
        records.append({"name": "finite_cap_failure_is_explicit", "state": "PASS"})
    else:
        raise AssertionError("one-iteration fictional cap should fail")
    for name, x, y in [("nonfinite_rejected", [[np.nan]], [1.]), ("shape_rejected", [[1., 2., 3.]], [1.])]:
        try:
            fit_lad(x, y)
        except ValueError:
            records.append({"name": name, "state": "PASS"})
        else:
            raise AssertionError("invalid fictional input accepted")
    path = Path("reports/next-nfl-checkpoint-lad-v1/FICTIONAL_SOLVER_CHECKS.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"state": "FICTIONAL_SOLVER_CHECKS_PASS", "NFL_reads": 0, "NFL_fits": 0, "HTTP": 0,
            "ADMM_fictional_fit_attempts": 7, "independent_QP_fictional_fits": 6, "invocations": 1,
            "checks": records, "CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - start,
            "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "state": body["state"]}))


if __name__ == "__main__":
    main()
