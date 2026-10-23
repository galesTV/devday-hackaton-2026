from sentinela_alimentos.collection import CollectionResult
from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.session_state import public_movements, save_public_result


def test_public_search_survives_marking_an_occurrence_reviewed():
    session: dict[str, object] = {"review_status": {"old": "Revisada"}}
    result = CollectionResult(sample_movements(), [], 0, False)

    save_public_result(session, result)
    session["review_status"]["pncp-001|Possível duplicidade"] = "Revisada"

    assert public_movements(session) == sample_movements()
    assert session["review_status"]["pncp-001|Possível duplicidade"] == "Revisada"
