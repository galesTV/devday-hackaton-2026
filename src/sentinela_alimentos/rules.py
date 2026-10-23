"""Auditável: sinais para revisão humana, nunca conclusões de fraude."""

from collections import defaultdict
from decimal import Decimal
from statistics import median

from .domain import Finding, FoodMovement
from .normalization import normalized_text

PRICE_MULTIPLIER = Decimal("1.5")
MIN_PRICE_REFERENCES = 3


def _same_optional(left: str | None, right: str | None) -> bool:
    """Optional context must not conflict; missing context is not a match claim."""
    return not left or not right or normalized_text(left) == normalized_text(right)


def effective_unit_price(movement: FoodMovement) -> Decimal | None:
    """Use the reported unit value or derive it safely from total ÷ quantity."""
    if movement.unit_price is not None:
        return movement.unit_price
    if movement.total_value is not None and movement.quantity not in (None, Decimal(0)):
        return movement.total_value / movement.quantity
    return None


def find_duplicate_movements(movements: list[FoodMovement]) -> list[Finding]:
    """Find repeated IDs and conservative near duplicates, retaining both IDs."""
    findings: list[Finding] = []
    by_id: dict[str, list[FoodMovement]] = defaultdict(list)
    for item in movements:
        if item.id:
            by_id[item.id].append(item)
    confirmed = {key: rows for key, rows in by_id.items() if len(rows) > 1}
    emitted: set[tuple[str, str]] = set()

    def add_pair(left: FoodMovement, right: FoodMovement, confirmed_id: bool = False) -> None:
        pair = tuple(sorted((left.id, right.id)))
        if pair in emitted:
            return
        emitted.add(pair)
        match_fields = ["id"] if confirmed_id else [
            "description", "supplier", "event_date", "total_value", "quantity", "unit"
        ]
        findings.append(Finding(
            left.id, "Possível duplicidade",
            f"{'ID repetido' if confirmed_id else 'Coincidência dos campos ' + ', '.join(match_fields)}; registros envolvidos: {left.id} e {right.id}.",
            "alta" if confirmed_id else "média", "duplicate_movement", "alert",
            {"kind": "confirmed_identifier" if confirmed_id else "similarity", "required_matches": match_fields},
            {"record_ids": sorted(set(pair)), "record_count": 2,
             "matched_fields": match_fields},
        ))

    for rows in confirmed.values():
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                add_pair(left, right, True)

    eligible = [item for item in movements if item.id not in confirmed and item.description and
                (item.supplier_id or item.supplier_name) and item.event_date and
                item.total_value is not None and item.quantity is not None and item.unit]
    for index, left in enumerate(eligible):
        for right in eligible[index + 1:]:
            same_supplier = ((left.supplier_id and right.supplier_id and left.supplier_id == right.supplier_id)
                             or (not left.supplier_id and not right.supplier_id and
                                 normalized_text(left.supplier_name) == normalized_text(right.supplier_name)))
            exact = (normalized_text(left.description) == normalized_text(right.description) and same_supplier and
                     left.event_date == right.event_date and left.total_value == right.total_value and
                     left.quantity == right.quantity and normalized_text(left.unit) == normalized_text(right.unit) and
                     _same_optional(left.buyer_name, right.buyer_name) and
                     _same_optional(left.municipality, right.municipality) and
                     _same_optional(left.state, right.state))
            if exact:
                add_pair(left, right)
    return findings


def find_outlier_prices(
    movements: list[FoodMovement], multiplier: Decimal = PRICE_MULTIPLIER
) -> list[Finding]:
    """Compare only exact text/category/unit and calendar-year peers."""
    findings: list[Finding] = []
    for item in movements:
        if not item.description or not item.unit or not item.category or not item.event_date:
            continue
        item_price = effective_unit_price(item)
        if item_price is None or not item_price.is_finite() or item_price <= 0:
            continue
        peers = [other for other in movements if other.id != item.id and other.description and other.unit and
                 other.category and other.event_date and effective_unit_price(other) is not None and
                 effective_unit_price(other).is_finite() and effective_unit_price(other) > 0 and
                 normalized_text(other.description) == normalized_text(item.description) and
                 normalized_text(other.category) == normalized_text(item.category) and
                 normalized_text(other.unit) == normalized_text(item.unit) and
                 other.event_date.year == item.event_date.year]
        common = {"multiplier": str(multiplier), "minimum_references": MIN_PRICE_REFERENCES,
                  "method": "mediana de referências válidas externas ao registro",
                  "comparison_fields": ["description", "category", "unit", "calendar_year"]}
        if len(peers) < MIN_PRICE_REFERENCES:
            findings.append(Finding(
                item.id, "Valor fora do critério",
                f"Evidência insuficiente: {len(peers)} referência(s) compatível(is); são necessárias {MIN_PRICE_REFERENCES}.",
                "informativa", "price_outlier", "insufficient_evidence", common,
                {"reference_count": len(peers), "reference_ids": [p.id for p in peers]},
                ["Sem amostra mínima não é possível avaliar atipicidade; isso não indica irregularidade."],
            ))
            continue
        reference = Decimal(str(median([effective_unit_price(peer) for peer in peers])))
        threshold = reference * multiplier
        if item_price > threshold:
            divergence = (item_price - reference) / reference * Decimal(100)
            findings.append(Finding(
                item.id, "Valor fora do critério",
                f"Preço unitário excede {multiplier}× a mediana compatível; sinal para revisão, não prova de irregularidade.",
                "média", "price_outlier", "alert", common,
                {"price": str(item_price), "reference_median": str(reference),
                 "threshold": str(threshold), "divergence_percent": str(divergence),
                 "reference_count": len(peers), "reference_ids": [p.id for p in peers],
                 "source_names": sorted({str(p.source) for p in peers})},
                ["Comparação textual exata de descrição, categoria e unidade; não há conversão de unidade."],
            ))
    return findings


def find_regional_price_discrepancies(
    purchases: list[FoodMovement],
    market_prices: list[FoodMovement],
    multiplier: Decimal = Decimal("1.30"),
) -> list[Finding]:
    """Compare against public price samples from the same municipality, then UF."""
    findings: list[Finding] = []
    for purchase in purchases:
        purchase_price = effective_unit_price(purchase)
        if purchase_price is None or purchase_price <= 0:
            continue
        municipal = [
            effective_unit_price(item)
            for item in market_prices
            if item.municipality_code == purchase.municipality_code
            and item.municipality_code
            and effective_unit_price(item) is not None
        ]
        state = [
            effective_unit_price(item)
            for item in market_prices
            if item.state == purchase.state and effective_unit_price(item) is not None
        ]
        samples = municipal or state
        if not samples:
            continue
        reference = Decimal(str(median(samples)))
        if purchase_price > reference * multiplier:
            scope = "município" if municipal else "UF"
            findings.append(Finding(
                purchase.id,
                "Possível discrepância regional de preço",
                "Preço unitário acima da referência regional; sinal para revisão, não prova de irregularidade.",
                "alta",
                "regional_price_discrepancy",
                "alert",
                {"multiplier": str(multiplier), "scope": scope},
                {"price": str(purchase_price), "reference_median": str(reference),
                 "reference_count": len(samples), "scope": scope},
                ["Verifique especificação, frete, sazonalidade e quantidade antes de concluir qualquer irregularidade."],
            ))
    return findings


def find_missing_required_data(movements: list[FoodMovement]) -> list[Finding]:
    findings: list[Finding] = []
    for item in movements:
        missing: list[str] = []
        invalid: list[str] = []
        if not item.id or not item.id.strip():
            missing.append("id")
        if not item.description or not item.description.strip():
            missing.append("description (duplicidade/preço)")
        if not item.supplier_id and not item.supplier_name:
            missing.append("supplier_id/supplier_name (duplicidade)")
        if item.event_date is None:
            missing.append("event_date (duplicidade/preço)")
        if item.total_value is None:
            missing.append("total_value (duplicidade)")
        if not item.unit:
            missing.append("unit (preço/duplicidade)")
        if not item.category:
            missing.append("category (preço)")
        if item.unit_price is None:
            missing.append("unit_price (preço)")
        elif not item.unit_price.is_finite() or item.unit_price <= 0:
            invalid.append("unit_price (deve ser finito e maior que zero)")
        if item.total_value is not None and (not item.total_value.is_finite() or item.total_value < 0):
            invalid.append("total_value (deve ser finito e não negativo)")
        absent = missing + invalid
        if absent:
            findings.append(Finding(
                item.id, "Informação obrigatória ausente", f"Dados ausentes ou inválidos: {', '.join(absent)}.",
                "média", "required_data", "alert",
                {"identity": ["id"], "duplicate": ["description", "supplier_id ou supplier_name", "event_date", "total_value", "quantity", "unit"],
                 "price": ["description", "category", "unit", "event_date", "unit_price"]},
                {"missing_fields": missing, "invalid_fields": invalid},
                ["Ausência ou invalidade limita a análise; não constitui evidência de fraude."],
            ))
    return findings


def run_all_rules(movements: list[FoodMovement]) -> list[Finding]:
    """Run all rules; insufficient price evidence is an explicit non-alert result."""
    return (find_duplicate_movements(movements) + find_outlier_prices(movements) +
            find_missing_required_data(movements))
