"""Orquestra coleta tolerante a falhas e remove repetições da mesma fonte."""

from dataclasses import dataclass
from datetime import date

import httpx

from .domain import FoodMovement, Source
from .live_data import (
    compras_food_catalog,
    compras_regional_market_prices,
    pncp_food_movements,
    transparency_food_agreements,
)
from .normalization import normalized_text

MAX_RECORDS = 100


@dataclass(frozen=True, slots=True)
class CollectionResult:
    movements: list[FoodMovement]
    errors: list[str]
    duplicates_removed: int
    truncated: bool


def movement_key(movement: FoodMovement) -> tuple[str, ...]:
    """Use the source identifier first; never merge records from different sources."""
    if movement.id:
        return (str(movement.source), movement.id)
    return (
        str(movement.source),
        normalized_text(movement.description),
        movement.supplier_id or normalized_text(movement.supplier_name),
        str(movement.event_date or ""),
        str(movement.quantity or ""),
        str(movement.unit_price or movement.total_value or ""),
        movement.municipality_code or normalized_text(movement.municipality),
    )


def deduplicate_movements(movements: list[FoodMovement]) -> tuple[list[FoodMovement], int]:
    """Keep first occurrence, retaining the provenance and fields of that raw record."""
    seen: set[tuple[str, ...]] = set()
    unique: list[FoodMovement] = []
    for movement in movements:
        key = movement_key(movement)
        if key in seen:
            continue
        seen.add(key)
        unique.append(movement)
    return unique, len(movements) - len(unique)


def collect_food_data(
    product: str, start: date, end: date, state: str | None = None
) -> CollectionResult:
    """Collect each official source independently so a source failure does not stop review."""
    records: list[FoodMovement] = []
    errors: list[str] = []
    for name, collector, arguments in [
        ("PNCP", pncp_food_movements, (start, end, product, state)),
        ("Compras.gov.br / CATMAT", compras_food_catalog, (product,)),
        ("Portal da Transparência", transparency_food_agreements, (start, end, state)),
    ]:
        try:
            records.extend(collector(*arguments))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            errors.append(f"{name}: {exc}")

    regions = {
        (item.state, item.municipality_code)
        for item in records
        if item.source is Source.PNCP
    }
    for region_state, municipality_code in regions:
        try:
            records.extend(
                compras_regional_market_prices(
                    product, region_state, municipality_code
                )
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            errors.append(f"Compras.gov.br / referência regional: {exc}")

    unique, removed = deduplicate_movements(records)
    truncated = len(unique) > MAX_RECORDS
    return CollectionResult(unique[:MAX_RECORDS], errors, removed, truncated)
