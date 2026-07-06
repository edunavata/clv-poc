"""Devig + cálculo de CLV. Matemática pura, sin storage ni red -- testeable con
un caso sintético sin necesitar partidos reales cerrados (Tarea 6).
"""


def implied_probability(decimal_odds: float) -> float:
    return 1 / decimal_odds


def devig(prices: dict[str, float]) -> dict[str, float]:
    """Normaliza las probabilidades implícitas del sharp book para que sumen 1.0
    (elimina el overround). Método multiplicativo básico -- no Shin's method.
    """
    raw = {outcome: implied_probability(odds) for outcome, odds in prices.items()}
    total = sum(raw.values())
    return {outcome: prob / total for outcome, prob in raw.items()}


def clv(captured_odds: float, sharp_fair_prob: float) -> float:
    """CLV = captured_odds * sharp_fair_prob - 1.

    >0 significa que el precio capturado batió el precio justo de cierre de
    la sharp (edge positivo); <0 significa que el cierre era mejor que lo
    que capturamos.
    """
    return captured_odds * sharp_fair_prob - 1
