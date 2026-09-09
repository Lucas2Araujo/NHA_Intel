"""
Módulo de views da interface gráfica (Flet) do Hinário App.
"""

from .agente_view import AgenteView
from .biblia_view import BibliaView
from .downloads_view import DownloadsView
from .hino_view import HinoView
from .home_view import HinosView, HomeView
from .selecao_view import SelecaoView

__all__ = [
    "AgenteView",
    "BibliaView",
    "DownloadsView",
    "HinoView",
    "HinosView",
    "HomeView",
    "SelecaoView",
]
