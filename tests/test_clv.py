import pytest

from analysis.clv import clv, devig, implied_probability

# Ejemplo sintético (no el de tenis del prompt original -- se perdió en la
# compactación de contexto de la sesión; este caso equivalente prueba lo
# mismo: overround conocido, de-vig correcto, signo de CLV correcto).
SHARP_CLOSING_ODDS = {"Team A": 1.80, "Team B": 2.05}


def test_implied_probability():
    assert implied_probability(2.0) == pytest.approx(0.5)


def test_devig_removes_overround_and_sums_to_one():
    fair_probs = devig(SHARP_CLOSING_ODDS)

    assert sum(fair_probs.values()) == pytest.approx(1.0)
    # La favorita (cuota más baja) debe seguir teniendo mayor probabilidad justa
    assert fair_probs["Team A"] > fair_probs["Team B"]


def test_clv_positive_when_captured_price_beats_fair_closing():
    fair_probs = devig(SHARP_CLOSING_ODDS)

    edge = clv(captured_odds=1.95, sharp_fair_prob=fair_probs["Team A"])

    assert edge > 0


def test_clv_negative_when_captured_price_is_worse_than_fair_closing():
    fair_probs = devig(SHARP_CLOSING_ODDS)

    edge = clv(captured_odds=1.70, sharp_fair_prob=fair_probs["Team A"])

    assert edge < 0


def test_clv_zero_at_exactly_fair_price():
    fair_probs = devig(SHARP_CLOSING_ODDS)
    fair_odds = 1 / fair_probs["Team A"]

    edge = clv(captured_odds=fair_odds, sharp_fair_prob=fair_probs["Team A"])

    assert edge == pytest.approx(0.0, abs=1e-9)
