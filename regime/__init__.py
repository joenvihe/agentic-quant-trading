"""Identificación y análisis de regímenes de mercado."""
"""Clasificación determinista e interpretable de regímenes de mercado."""

from regime.engine import RegimeAssessment, RegimeError, detect_regime
from regime.comparison import RegimeComparison, compare_regimes
from regime.hmm import (
    GaussianHMMRegime,
    HMMRegimeError,
    HMMRegimeResult,
    HMMStateStatistics,
)

__all__ = [
    "GaussianHMMRegime",
    "HMMRegimeError",
    "HMMRegimeResult",
    "HMMStateStatistics",
    "RegimeAssessment",
    "RegimeComparison",
    "RegimeError",
    "compare_regimes",
    "detect_regime",
]
