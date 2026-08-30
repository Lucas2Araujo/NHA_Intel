"""
Módulo de repositórios do Hinário App.
"""

from .comparativo_repository import ComparativoRepository
from .culto_repository import CultoRepository
from .favorito_repository import FavoritoRepository
from .hino_repository import HinoRepository
from .historico_repository import HistoricoRepository

__all__ = [
    "ComparativoRepository",
    "CultoRepository",
    "FavoritoRepository",
    "HinoRepository",
    "HistoricoRepository",
]
