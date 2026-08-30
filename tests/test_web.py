import main
import web


def test_web_module_imports():
    assert hasattr(web, "main")
    assert web.main is main.main
