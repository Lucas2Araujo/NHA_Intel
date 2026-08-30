import main
from src.version import __version__
from src.views.home_view import APP_VERSION as HOME_APP_VERSION


def test_version_defined():
    """Valida se __version__ está definida e não vazia."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0
    assert "." in __version__


def test_version_imported_in_views():
    """Valida se a versão é importada corretamente nas views e módulo principal."""
    assert HOME_APP_VERSION == __version__
    assert main.APP_VERSION == __version__
