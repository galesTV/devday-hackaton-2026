from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_ai_page_is_available_without_making_a_provider_call(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run()

    app.radio(key="page_navigation").set_value("Análise com IA").run()
    app.multiselect[0].set_value([app.multiselect[0].options[0]]).run()

    assert not app.exception
    assert any(button.label == "Analisar com IA" for button in app.button)
    assert app.multiselect[0].label == "Registros para análise (até 5)"
