import tomllib
from pathlib import Path

import main
from src.services.updater_service import APP_VERSION as UPDATER_APP_VERSION
from src.version import __version__
from src.views.agente_view import APP_VERSION as AGENTE_APP_VERSION
from src.views.home_view import APP_VERSION as HOME_APP_VERSION
from src.views.selecao_view import APP_VERSION as SELECAO_APP_VERSION
from src.views.settings_dialog import APP_VERSION as SETTINGS_APP_VERSION


def test_version_defined():
    """Valida se __version__ está definida e não vazia."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0
    assert "." in __version__


def test_version_imported_in_views():
    """Valida se a versão é importada corretamente nas views e módulo principal."""
    assert HOME_APP_VERSION == __version__
    assert main.APP_VERSION == __version__
    assert SELECAO_APP_VERSION == __version__
    assert SETTINGS_APP_VERSION == __version__
    assert UPDATER_APP_VERSION == __version__
    assert AGENTE_APP_VERSION == __version__


def test_pyproject_toml_version_sync():
    """Valida que a versão no pyproject.toml está sincronizada com src.version.__version__."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == __version__
