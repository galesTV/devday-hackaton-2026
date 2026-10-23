"""Regras pequenas, auditáveis e explicitamente não conclusivas."""

from collections import defaultdict
from decimal import Decimal
from statistics import median

from .domain import Finding, FoodMovement
from .normalization import normalized_text

REQUIRED_FIELDS = {"descrição": "description", "fornecedor": "supplier_name", "valor total": "total_value"}


def find_duplicate_movements(movements: list[FoodMovement]) -> list[Finding]:
    groups: dict[tuple[str, str, Decimal | None, object], list[FoodMovement]] = defaultdict(list)
    for movement in movements:
        key = (normalized_text(movement.description), movement.supplier_id or normalized_text(movement.supplier_name), movement.total_value, movement.event_date)
        groups[key].append(movement)
    findings: list[Finding] = []
    for group in groups.values():
        if len(group) > 1 and group[0].total_value is not None:
            ids = ", ".join(item.id for item in group)
            for item in group:
                findings.append(Finding(item.id, "Possível duplicidade", f"Mesmo item, fornecedor, valor e data que os registros: {ids}.", "alta"))
    return findings


def find_outlier_prices(movements: list[FoodMovement], multiplier: Decimal = Decimal("1.5")) -> list[Finding]:
    by_item: dict[tuple[str, str], list[FoodMovement]] = defaultdict(list)
    for movement in movements:
        if movement.unit_price is not None and movement.unit_price > 0:
            by_item[(normalized_text(movement.description), normalized_text(movement.unit))].append(movement)
    findings: list[Finding] = []
    for group in by_item.values():
        if len(group) < 3:
            continue
        reference = Decimal(str(median([item.unit_price for item in group if item.unit_price])))
        threshold = reference * multiplier
        for item in group:
            if item.unit_price and item.unit_price > threshold:
                findings.append(Finding(item.id, "Valor fora do critério", f"Preço unitário R$ {item.unit_price:.2f} supera 1,5× a mediana comparável de R$ {reference:.2f}.", "média"))
    return findings


def find_missing_required_data(movements: list[FoodMovement]) -> list[Finding]:
    findings: list[Finding] = []
    for item in movements:
        missing = [label for label, field in REQUIRED_FIELDS.items() if getattr(item, field) is None or getattr(item, field) == ""]
        if missing:
            findings.append(Finding(item.id, "Informação obrigatória ausente", f"Campo(s) ausente(s): {', '.join(missing)}.", "média"))
    return findings


def run_all_rules(movements: list[FoodMovement]) -> list[Finding]:
    return find_duplicate_movements(movements) + find_outlier_prices(movements) + find_missing_required_data(movements)
