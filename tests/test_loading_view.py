import flet as ft
from main import _build_loading_view


def test_build_loading_view():
    view = _build_loading_view(0.5)
    assert isinstance(view, ft.View)
    assert view.route == "/loading"
    assert view.bgcolor == ft.Colors.SURFACE
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)
    assert view.controls[0].maintain_bottom_view_padding is True
