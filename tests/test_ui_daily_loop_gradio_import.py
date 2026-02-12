import importlib


def test_import_ui_daily_loop_gradio_smoke() -> None:
    module = importlib.import_module("scripts.ui_daily_loop_gradio")
    assert module is not None
