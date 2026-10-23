"""Funções puras para persistir o resultado da busca durante reruns do Streamlit."""

from collections.abc import MutableMapping

from .collection import CollectionResult
from .domain import FoodMovement

LIVE_RESULT_KEY = "live_result"


def save_public_result(
    session: MutableMapping[str, object], result: CollectionResult
) -> None:
    session[LIVE_RESULT_KEY] = result
    session["live_search_completed"] = True
    session["review_status"] = {}


def public_movements(session: MutableMapping[str, object]) -> list[FoodMovement]:
    result = session.get(LIVE_RESULT_KEY)
    return result.movements if isinstance(result, CollectionResult) else []
