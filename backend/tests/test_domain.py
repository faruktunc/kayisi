import numpy as np
import pytest

from app.domain.design import generators as g
from app.domain.design.catalog import DESIGN_SPECS
from app.domain.design.criteria import design_criteria
from app.domain.design.model_matrix import cube_moment_matrix, model_matrix
from app.domain.evaluation.desirability import Goals
from app.domain.evaluation.monte_carlo import TruthReference, evaluate_design
from app.domain.process.model import ModelParameters, ProcessSettings, ProcessSimulator
from app.domain.shared.factors import FACTORS, coded_to_natural, natural_to_coded


def test_coding_roundtrip():
    X = np.random.default_rng(0).uniform(-1, 1, (10, 6))
    assert np.allclose(natural_to_coded(coded_to_natural(X)), X)
    assert coded_to_natural(-np.ones((1, 6)))[0, 0] == FACTORS[0].low


def test_quadratic_model_has_28_terms():
    assert model_matrix(np.zeros((1, 6))).shape == (1, 28)


def test_moment_matrix_matches_monte_carlo():
    pts = np.random.default_rng(1).uniform(-1, 1, (200_000, 6))
    F = model_matrix(pts)
    assert np.allclose(F.T @ F / len(pts), cube_moment_matrix(), atol=0.01)


@pytest.mark.parametrize("key,n", [("ccd_half", 50), ("ccd_full", 82), ("bbd", 54), ("d_opt_36", 40), ("i_opt_42", 42)])
def test_design_sizes_and_bounds(key, n):
    X = DESIGN_SPECS[key].builder()
    assert X.shape == (n, 6)
    assert np.all(np.abs(X) <= 1 + 1e-9)
    assert design_criteria(X)["estimable"]


def test_d_optimal_has_center_replicates_for_pure_error():
    for key in ("d_opt_30", "d_opt_36", "d_opt_42"):
        c = design_criteria(DESIGN_SPECS[key].builder())
        assert c["n_center"] >= 4
        assert c["df_pure_error"] >= 3


def test_bbd_points_have_three_active_factors():
    X = g.box_behnken_6(0)
    assert np.all(np.sum(X != 0, axis=1) == 3)


def test_d_optimal_beats_random_selection():
    cand = g.three_level_grid()
    rng = np.random.default_rng(3)
    random_logdets = []
    for _ in range(20):
        F = model_matrix(cand[rng.choice(len(cand), 36, replace=False)])
        random_logdets.append(np.linalg.slogdet(F.T @ F)[1])
    F = model_matrix(g.optimal_design(36, "D", seed=0))
    assert np.linalg.slogdet(F.T @ F)[1] > max(random_logdets)


def test_simulator_physical_trends():
    sim = ProcessSimulator(ModelParameters())
    base = coded_to_natural(np.zeros((1, 6)))
    st = ProcessSettings()

    def resp(col, value, key):
        X = base.copy()
        X[0, col] = value
        return sim.run(X, st)[key][0]

    # Daha yüksek H₂O₂ ve daha uzun süre -> daha az SO₂
    assert resp(1, 1.5, "so2_final") < resp(1, 0.5, "so2_final")
    assert resp(2, 15, "so2_final") < resp(2, 5, "so2_final")
    # Daha sıcak ve daha düşük basınç -> daha kısa kurutma
    assert resp(4, 60, "drying_time") < resp(4, 30, "drying_time")
    assert resp(5, 400, "drying_time") < resp(5, 560, "drying_time")
    # Kurutma hedef nemde biter
    assert sim.run(base, st)["moisture_final"][0] == pytest.approx(st.target_moisture)


def test_more_applications_reduce_so2():
    sim = ProcessSimulator()
    X = coded_to_natural(np.zeros((1, 6)))
    one = sim.run(X, ProcessSettings(n_applications=1))["so2_final"][0]
    two = sim.run(X, ProcessSettings(n_applications=2))["so2_final"][0]
    assert two < one


def test_monte_carlo_regret_is_small_for_good_design_and_nonnegative():
    sim, st, goals = ProcessSimulator(), ProcessSettings(), Goals()
    truth = TruthReference.build(sim, st, goals, n_test=500)
    good = evaluate_design(DESIGN_SPECS["ccd_half"].builder(), sim, st, goals, truth, n_reps=30)
    poor = evaluate_design(DESIGN_SPECS["lhs_30"].builder(), sim, st, goals, truth, n_reps=30)
    assert good["regret_mean"] >= 0
    assert good["regret_mean"] < poor["regret_mean"]
