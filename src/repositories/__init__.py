"""
Módulo de repositórios do Hinário App.
"""

from .hino_repository import HinoRepository
from .favorito_repository import FavoritoRepository
from .historico_repository import HistoricoRepository
from .culto_repository import CultoRepository
from .biblia_repository import BibliaRepository

__all__ = [
    "HinoRepository",
    "FavoritoRepository",
    "HistoricoRepository",
    "CultoRepository",
    "BibliaRepository",
]
