"""Géométrie vectorisée : séparation, espace devant, point de réception, YAC Potential."""
import numpy as np
import pytest

from tracker import config as C
from tracker.metrics import (
    direct_defender, distances, estimate_landing, nearest_to_point, route_separations, separation, space_ahead,
    yac_potential,
)


def test_separation_is_distance_to_nearest_defender():
    sep, nearest = separation(np.array([0.0, 0.0]), np.array([[3.0, 4.0], [10.0, 0.0]]))
    assert sep == pytest.approx(5.0) and nearest == 0


def test_separation_is_vectorised_over_time():
    receiver = np.array([[0.0, 0.0], [0.0, 0.0]])                 # 2 images
    defenders = np.array([[[3.0, 4.0], [10.0, 0.0]], [[1.0, 0.0], [10.0, 0.0]]])
    sep, nearest = separation(receiver, defenders)
    assert sep == pytest.approx([5.0, 1.0]) and list(nearest) == [0, 0]


def test_route_separations_one_value_per_receiver():
    routes = np.array([[[0.0, 0.0], [20.0, 0.0]]])                # 1 image, 2 receveurs
    defenders = np.array([[[0.0, 2.0], [20.0, 5.0]]])
    assert route_separations(routes, defenders)[0] == pytest.approx([2.0, 5.0])
    assert distances(np.array([0.0, 0.0]), np.array([[3.0, 4.0]]))[0] == pytest.approx(5.0)


def test_space_ahead_ignores_defenders_behind():
    receiver = np.array([30.0, 26.0])
    defenders = np.array([[29.0, 26.0], [36.0, 26.0], [32.0, 40.0]])      # derrière, 6 yd devant, loin devant
    assert space_ahead(receiver, defenders) == pytest.approx(6.0)
    assert space_ahead(receiver, defenders[:1]) == C.SPACE_CAP              # personne devant -> plafond


def test_direct_defender_is_the_one_who_sticks():
    receiver = np.array([[x, 26.0] for x in range(10, 20)], dtype=float)
    shadow = receiver + [0.0, 1.0]
    far = receiver + [15.0, 0.0]
    defenders = np.stack([far, shadow], axis=1)                   # (images, 2, 2)
    assert direct_defender(receiver, defenders, 0, 9) == 1


def test_nearest_to_point():
    dist, idx = nearest_to_point(np.array([[0.0, 0.0], [5.0, 0.0]]), np.array([4.0, 0.0]))
    assert dist == pytest.approx(1.0) and idx == 1


def _flight(frames=8):
    """Ballon à 20 yd/s vers +x depuis l'origine, receveur immobile à 20 yd."""
    ball = np.array([[2.0 * k, 0.0] for k in range(frames)])      # 2 yd par image = 20 yd/s
    receiver = np.tile([20.0, 0.0], (frames, 1))
    return ball, receiver


def test_estimate_landing_meets_the_receiver():
    ball, receiver = _flight()
    landing = estimate_landing(ball, receiver, release_idx=0, last_idx=5)
    assert not landing.observed
    assert landing.xy == pytest.approx((20.0, 0.0), abs=0.5)
    assert landing.seconds == pytest.approx(1.0, abs=0.05)


def test_estimate_landing_uses_observed_arrival():
    ball, receiver = _flight()
    landing = estimate_landing(ball, receiver, release_idx=0, last_idx=5, arrival_idx=4)
    assert landing.observed and landing.xy == (8.0, 0.0) and landing.seconds == pytest.approx(0.4)


def test_estimate_landing_falls_back_to_the_receiver_when_data_is_too_short():
    ball, receiver = _flight()
    landing = estimate_landing(ball, receiver, release_idx=4, last_idx=5)
    assert landing.xy == (20.0, 0.0) and not landing.observed


def test_yac_potential_grows_with_space_and_is_bounded():
    low = yac_potential(1.0, 2.0, 1.0, 40.0)
    high = yac_potential(6.0, 15.0, 8.0, 40.0)
    assert 0.0 <= low < high
    assert yac_potential(8.0, 15.0, 9.0, 108.0) <= 2.0 + 1e-9      # plafonné par la distance à la ligne de but
    assert yac_potential(0.0, 0.0, 0.0, 40.0) == 0.0                # jamais négatif
    arr = yac_potential(np.array([1.0, 5.0]), np.array([4.0, 10.0]), np.array([2.0, 6.0]), np.array([30.0, 30.0]))
    assert arr.shape == (2,) and arr[0] < arr[1]
