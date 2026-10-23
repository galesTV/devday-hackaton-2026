"""Regras pequenas, auditáveis e explicitamente não conclusivas."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from .domain import Finding, FoodMovement
from .normalization import normalized_text

PRICE_MULTIPLIER = Decimal("1.5")
MIN_PRICE_REFERENCES = 3


def _valid_positive_decimal(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def _valid_nonnegative_decimal(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


def _median(values: list[Decimal]) -> Decimal:
    """Return an exact Decimal median without converting through binary float."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _optional_context_matches(left: str | None, right: str | None) -> bool:
    """Available context must agree; missing optional context does not conflict."""
    return not left or not right or normalized_text(left) == normalized_text(right)


def _supplier_matches(left: FoodMovement, right: FoodMovement) -> bool:
    if left.supplier_id and right.supplier_id:
        return normalized_text(left.supplier_id) == normalized_text(right.supplier_id)
    if not left.supplier_id and not right.supplier_id:
        return bool(left.supplier_name and right.supplier_name) and (
            normalized_text(left.supplier_name) == normalized_text(right.supplier_name)
        )
    return False


def find_duplicate_movements(movements: list[FoodMovement]) -> list[Finding]:
    """Find repeated record IDs and conservative matching movement pairs."""
    findings: list[Finding] = []
    by_id: dict[str, list[tuple[int, FoodMovement]]] = defaultdict(list)
    for record_index, item in enumerate(movements):
        if item.id and item.id.strip():
            by_id[item.id].append((record_index, item))

    repeated_ids = {record_id: rows for record_id, rows in by_id.items() if len(rows) > 1}
    emitted_pairs: set[tuple[int, int]] = set()

    def add_pair(
        left: FoodMovement,
        right: FoodMovement,
        left_index: int,
        right_index: int,
        kind: str,
        matched_fields: list[str],
        limitations: list[str] | None = None,
    ) -> None:
        pair_key = tuple(sorted((left_index, right_index)))
        if pair_key in emitted_pairs:
            return
        emitted_pairs.add(pair_key)
        record_ids = [left.id, right.id]
        evidence = {
            "record_ids": record_ids,
            "matched_fields": matched_fields,
            "sources": [str(left.source), str(right.source)],
            "source_urls": [left.source_url, right.source_url],
        }
        for current, other in ((left, right), (right, left)):
            findings.append(Finding(
                movement_id=current.id,
                rule="Possível duplicidade",
                explanation=(
                    f"{other.id} compartilha {', '.join(matched_fields)}; "
                    "sinal para revisão, não confirmação de irregularidade."
                ),
                severity="média",
                rule_id="duplicate_movement",
                alert_type="alert",
                criteria={"kind": kind, "required_matches": matched_fields},
                evidence={**evidence, "related_record_id": other.id},
                limitations=limitations or [],
            ))

    for rows in repeated_ids.values():
        for index, (left_index, left) in enumerate(rows):
            for right_index, right in rows[index + 1:]:
                add_pair(
                    left, right, left_index, right_index,
                    "repeated_identifier_candidate", ["id"],
                    ["O modelo não garante ID globalmente único; validar a chave e o documento na fonte."],
                )

    eligible = [
        (record_index, item) for record_index, item in enumerate(movements)
        if item.id and item.id.strip() and item.id not in repeated_ids
        and item.description and item.description.strip()
        and (item.supplier_id and item.supplier_id.strip()
             or item.supplier_name and item.supplier_name.strip())
        and isinstance(item.event_date, date)
        and _valid_nonnegative_decimal(item.total_value)
        and isinstance(item.quantity, Decimal) and item.quantity.is_finite()
        and item.quantity >= 0 and item.unit and item.unit.strip()
    ]
    matched_fields = [
        "description", "supplier_id/name", "event_date", "total_value",
        "quantity", "unit",
    ]
    for index, (left_index, left) in enumerate(eligible):
        for right_index, right in eligible[index + 1:]:
            if (
                normalized_text(left.description) == normalized_text(right.description)
                and _supplier_matches(left, right)
                and left.event_date == right.event_date
                and left.total_value == right.total_value
                and left.quantity == right.quantity
                and normalized_text(left.unit) == normalized_text(right.unit)
                and _optional_context_matches(left.buyer_name, right.buyer_name)
                and _optional_context_matches(left.municipality, right.municipality)
                and _optional_context_matches(left.state, right.state)
            ):
                missing_context = [
                    field for field in ("buyer_name", "municipality", "state")
                    if not getattr(left, field) or not getattr(right, field)
                ]
                add_pair(
                    left, right, left_index, right_index, "similarity", matched_fields,
                    [f"Contexto opcional ausente: {', '.join(missing_context)}"]
                    if missing_context else [],
                )
    return findings


def _comparable(item: FoodMovement, candidate: FoodMovement) -> bool:
    """Require exact product, unit, quarter, and locality comparability."""
    return bool(
        item.id and item.id.strip() and candidate.id and candidate.id.strip()
        and candidate.id != item.id
        and item.description and item.description.strip()
        and item.category and item.category.strip()
        and item.unit and item.unit.strip()
        and isinstance(item.event_date, date)
        and item.state and item.state.strip()
        and item.municipality and item.municipality.strip()
        and candidate.description and candidate.description.strip()
        and candidate.category and candidate.category.strip()
        and candidate.unit and candidate.unit.strip()
        and isinstance(candidate.event_date, date)
        and candidate.state and candidate.state.strip()
        and candidate.municipality and candidate.municipality.strip()
        and _valid_positive_decimal(candidate.unit_price)
        and normalized_text(item.description) == normalized_text(candidate.description)
        and normalized_text(item.category) == normalized_text(candidate.category)
        and normalized_text(item.unit) == normalized_text(candidate.unit)
        and item.event_date.year == candidate.event_date.year
        and (item.event_date.month - 1) // 3 == (candidate.event_date.month - 1) // 3
        and normalized_text(item.state) == normalized_text(candidate.state)
        and normalized_text(item.municipality) == normalized_text(candidate.municipality)
    )


def find_outlier_prices(
    movements: list[FoodMovement], multiplier: Decimal = PRICE_MULTIPLIER
) -> list[Finding]:
    """Flag high prices versus median of at least three local, quarterly peers.

    The existing 1.5 multiplier is a configurable MVP screening threshold,
    not a universal market or legal standard.
    """
    try:
        configured_multiplier = Decimal(str(multiplier))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("multiplier must be a finite Decimal greater than zero") from error
    if not configured_multiplier.is_finite() or configured_multiplier <= 0:
        raise ValueError("multiplier must be a finite Decimal greater than zero")

    findings: list[Finding] = []
    id_counts: dict[str, int] = defaultdict(int)
    for record in movements:
        if record.id:
            id_counts[record.id] += 1
    for item in movements:
        if not (
            item.id and item.id.strip() and item.description and item.description.strip()
            and item.category and item.category.strip() and item.unit and item.unit.strip()
            and isinstance(item.event_date, date) and item.state and item.state.strip()
            and item.municipality and item.municipality.strip()
            and _valid_positive_decimal(item.unit_price)
        ):
            continue
        # A repeated identifier makes it impossible to tie a price finding to
        # one unambiguous source row. The duplicate rule reports that issue.
        if id_counts[item.id] != 1:
            continue
        peers = [
            candidate for candidate in movements
            if id_counts[candidate.id] == 1 and _comparable(item, candidate)
        ]
        common_criteria = {
            "multiplier": str(configured_multiplier),
            "minimum_references": MIN_PRICE_REFERENCES,
            "method": "mediana exata das referências externas válidas",
            "comparison_fields": [
                "description", "category", "unit", "calendar_quarter",
                "state", "municipality",
            ],
        }
        if len(peers) < MIN_PRICE_REFERENCES:
            findings.append(Finding(
                movement_id=item.id,
                rule="Valor fora do critério",
                explanation=(
                    f"Evidência insuficiente: {len(peers)} referência(s) comparável(is); "
                    f"mínimo exigido: {MIN_PRICE_REFERENCES}."
                ),
                severity="informativa",
                rule_id="price_outlier",
                alert_type="insufficient_evidence",
                criteria=common_criteria,
                evidence={
                    "price": str(item.unit_price),
                    "reference_count": len(peers),
                    "reference_ids": [peer.id for peer in peers],
                },
                limitations=[
                    "Sem referências suficientes, não é possível avaliar atipicidade.",
                    "O modelo não contém especificação estruturada; exige descrição e categoria exatas.",
                    "Referências com ID repetido foram excluídas para evitar contagem duplicada.",
                ],
            ))
            continue

        reference = _median([peer.unit_price for peer in peers])
        threshold = reference * configured_multiplier
        if item.unit_price > threshold:
            divergence = (item.unit_price - reference) / reference * Decimal(100)
            findings.append(Finding(
                movement_id=item.id,
                rule="Valor fora do critério",
                explanation=(
                    f"Preço {item.unit_price} excede {configured_multiplier}× "
                    f"a mediana de {reference} ({divergence:.2f}% acima); "
                    "sinal para investigação, não prova de fraude."
                ),
                severity="média",
                rule_id="price_outlier",
                alert_type="alert",
                criteria=common_criteria,
                evidence={
                    "price": str(item.unit_price),
                    "reference_median": str(reference),
                    "threshold": str(threshold),
                    "divergence_percent": str(divergence),
                    "reference_count": len(peers),
                    "reference_ids": [peer.id for peer in peers],
                    "reference_sources": sorted({str(peer.source) for peer in peers}),
                },
                limitations=[
                    "Unidades não são convertidas; a descrição e categoria são comparadas textualmente.",
                    "O multiplicador é um critério de triagem configurável, não um padrão universal.",
                    "Referências com ID repetido foram excluídas para evitar contagem duplicada.",
                ],
            ))
    return findings


def find_missing_required_data(movements: list[FoodMovement]) -> list[Finding]:
    """Report absent or invalid fields needed for identity and rule execution."""
    findings: list[Finding] = []
    for item in movements:
        missing: list[str] = []
        invalid: list[str] = []
        if not item.id or not item.id.strip():
            missing.append("id (rastreabilidade)")
        if not item.description or not item.description.strip():
            missing.append("description (comparação de produto/duplicidade)")
        if not (item.supplier_id and item.supplier_id.strip()) and not (
            item.supplier_name and item.supplier_name.strip()
        ):
            missing.append("supplier_id ou supplier_name (duplicidade)")
        if not isinstance(item.event_date, date):
            missing.append("event_date (duplicidade/preço)")
        if not isinstance(item.quantity, Decimal):
            missing.append("quantity (duplicidade)")
        elif not item.quantity.is_finite() or item.quantity < 0:
            invalid.append("quantity (deve ser finita e não negativa)")
        if not item.unit or not item.unit.strip():
            missing.append("unit (duplicidade/preço)")
        if not _valid_nonnegative_decimal(item.total_value):
            if item.total_value is None:
                missing.append("total_value (duplicidade)")
            else:
                invalid.append("total_value (deve ser finito e não negativo)")
        if not item.category or not item.category.strip():
            missing.append("category (comparabilidade de preço)")
        if item.unit_price is None:
            missing.append("unit_price (preço)")
        elif not _valid_positive_decimal(item.unit_price):
            invalid.append("unit_price (deve ser finito e maior que zero)")
        if not item.state or not item.state.strip():
            missing.append("state (comparabilidade de preço)")
        if not item.municipality or not item.municipality.strip():
            missing.append("municipality (comparabilidade de preço)")

        if missing or invalid:
            findings.append(Finding(
                movement_id=item.id,
                rule="Informação obrigatória ausente",
                explanation=(
                    "Dados necessários ausentes ou inválidos: "
                    f"{', '.join(missing + invalid)}. Isso limita a análise e não indica fraude."
                ),
                severity="média",
                rule_id="required_data",
                alert_type="alert",
                criteria={
                    "identity": ["id"],
                    "duplicate": [
                        "description", "supplier_id ou supplier_name", "event_date",
                        "total_value", "quantity", "unit",
                    ],
                    "price": [
                        "description", "category", "unit", "event_date",
                        "state", "municipality", "unit_price",
                    ],
                },
                evidence={"missing_fields": missing, "invalid_fields": invalid},
                limitations=["A falta de informação não constitui evidência de fraude."],
            ))
    return findings


def run_all_rules(movements: list[FoodMovement]) -> list[Finding]:
    """Run the three rules and return findings tied to source movement IDs."""
    return (
        find_duplicate_movements(movements)
        + find_outlier_prices(movements)
        + find_missing_required_data(movements)
    )
