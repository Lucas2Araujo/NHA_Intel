"""
Módulo de modelos de dados do Hinário App.
"""

from .hino import Hino
from .comparativo import HinoComparativo, BlocoDiff, EstatisticasDiff

__all__ = ["Hino", "HinoComparativo", "BlocoDiff", "EstatisticasDiff"]
