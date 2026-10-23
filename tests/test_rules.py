from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from sentinela_alimentos.demo_data import movement, sample_movements
<<<<<<< Updated upstream
=======
from sentinela_alimentos.domain import Source
>>>>>>> Stashed changes
from sentinela_alimentos.rules import (
    find_duplicate_movements,
    find_missing_required_data,
    find_outlier_prices,
    run_all_rules,
)


@pytest.fixture
<<<<<<< Updated upstream
def item_factory():
    def make(id, price="10", **kwargs):
        base = movement(id, "Arroz tipo 1", price, str(Decimal(price or "0") * 10))
        return replace(base, category="Arroz", quantity=Decimal(10), unit="kg",
                       event_date=date(2026, 6, 1), **kwargs)
    return make


def test_duplicate_similarity_and_evidence(item_factory):
    rows = [item_factory("a"), item_factory("b")]
    findings = find_duplicate_movements(rows)
    assert len(findings) == 1
    assert findings[0].evidence["record_ids"] == ["a", "b"]
    assert findings[0].evidence["matched_fields"] == [
        "description", "supplier", "event_date", "total_value", "quantity", "unit"
    ]
    assert findings[0].criteria["kind"] == "similarity"


def test_same_value_alone_is_not_duplicate(item_factory):
    rows = [item_factory("a"), item_factory("b", supplier_name="Outra", supplier_id="456")]
    assert not find_duplicate_movements(rows)


def test_incomplete_records_cannot_be_similarity_duplicates(item_factory):
    rows = [item_factory("a", supplier_name=None, supplier_id=None),
            item_factory("b", supplier_name=None, supplier_id=None)]
    assert not find_duplicate_movements(rows)


def test_repeated_id_is_confirmed(item_factory):
    finding = find_duplicate_movements([item_factory("same"), item_factory("same")])[0]
    assert finding.criteria["kind"] == "confirmed_identifier"
    assert finding.evidence["record_ids"] == ["same"]


def test_outlier_uses_three_external_comparable_references(item_factory):
    rows = [item_factory("a", "10"), item_factory("b", "10"), item_factory("c", "10"),
            item_factory("target", "20")]
    findings = find_outlier_prices(rows)
    outlier = next(f for f in findings if f.movement_id == "target")
    assert outlier.alert_type == "alert"
    assert Decimal(outlier.evidence["reference_median"]) == 10
    assert Decimal(outlier.evidence["divergence_percent"]) == 100
    assert outlier.evidence["reference_count"] == 3


@pytest.mark.parametrize("target", ["10", "15"])
def test_price_at_or_within_threshold_has_no_outlier(item_factory, target):
    rows = [item_factory("a", "10"), item_factory("b", "10"), item_factory("c", "10"),
            item_factory("target", target)]
    assert not [f for f in find_outlier_prices(rows)
                if f.movement_id == "target" and f.alert_type == "alert"]


def test_units_specs_period_and_insufficient_are_not_mixed(item_factory):
    target = item_factory("target", "100")
    peers = [item_factory("a"), item_factory("b"), item_factory("c")]
    different = [replace(peer, id=f"{peer.id}-diff", unit="pacote") for peer in peers]
    assert next(f for f in find_outlier_prices([target, *different])
                if f.movement_id == "target").alert_type == "insufficient_evidence"
    category_diff = [replace(peer, id=f"{peer.id}-cat", category="Outro") for peer in peers]
    assert next(f for f in find_outlier_prices([target, *category_diff])
                if f.movement_id == "target").alert_type == "insufficient_evidence"
    old = [replace(peer, id=f"{peer.id}-old", event_date=date(2024, 1, 1)) for peer in peers]
    assert next(f for f in find_outlier_prices([target, *old])
                if f.movement_id == "target").alert_type == "insufficient_evidence"


def test_missing_fields_and_optional_field(item_factory):
    original = item_factory("x")
    missing_description = replace(original, description=None)
    finding = find_missing_required_data([missing_description])[0]
    assert "description (duplicidade/preço)" in finding.evidence["missing_fields"]
    assert not find_missing_required_data([replace(original, source_url=None, municipality=None)])


def test_multiple_missing_fields_are_reported(item_factory):
    row = replace(item_factory("x"), description=None, supplier_name=None,
                  supplier_id=None, unit=None, unit_price=None, total_value=None,
                  category=None, event_date=None)
    finding = find_missing_required_data([row])[0]
    assert len(finding.evidence["missing_fields"]) >= 7


def test_run_all_rules_consistent_and_associated_to_source():
    findings = run_all_rules(sample_movements() + [movement("isolated", "Feijão", "12", "120")])
    assert all(f.movement_id and f.rule_id and f.alert_type in {"alert", "insufficient_evidence"}
               for f in findings)
    assert {f.rule for f in findings if f.alert_type == "alert"} == {
        "Possível duplicidade", "Valor fora do critério", "Informação obrigatória ausente"
    }
    assert any(f.alert_type == "insufficient_evidence" for f in findings)
    assert all(f.explanation and isinstance(f.evidence, dict) for f in findings)
=======
def make_movement():
    def make(
        record_id: str,
        price: Decimal | str = "10",
        *,
        description: str | None = "Arroz tipo 1",
        category: str | None = "Cereais",
        unit: str | None = "kg",
        supplier_id: str | None = "123",
        supplier_name: str | None = "Fornecedor A",
        event_date: date | None = date(2026, 2, 10),
        quantity: Decimal | None = Decimal(10),
        total_value: Decimal | None = Decimal(100),
        municipality: str | None = "Brasília",
        state: str | None = "DF",
        source: Source = Source.PNCP,
    ):
        base = movement(
            record_id, description, str(price), str(total_value or Decimal(0)),
            supplier=supplier_name, source=source,
        )
        return replace(
            base,
            category=category,
            unit=unit,
            supplier_id=supplier_id,
            event_date=event_date,
            quantity=quantity,
            unit_price=price if isinstance(price, Decimal) else Decimal(price),
            total_value=total_value,
            municipality=municipality,
            state=state,
        )

    return make


def test_duplicate_pair_has_structured_evidence_for_both_records(make_movement):
    findings = find_duplicate_movements(
        [make_movement("a"), make_movement("b", source=Source.COMPRAS_GOV)]
    )
    assert {finding.movement_id for finding in findings} == {"a", "b"}
    assert all(finding.rule_id == "duplicate_movement" for finding in findings)
    assert all(finding.evidence["record_ids"] == ["a", "b"] for finding in findings)
    assert all(finding.evidence["sources"] == ["PNCP", "Compras.gov.br"]
               for finding in findings)
    assert all("quantity" in finding.evidence["matched_fields"] for finding in findings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": None},
        {"description": "   "},
        {"supplier_id": None, "supplier_name": None},
        {"event_date": None},
        {"quantity": None},
        {"unit": None},
    ],
)
def test_duplicate_skips_records_missing_required_match_fields(make_movement, overrides):
    assert not find_duplicate_movements(
        [make_movement("a", **overrides), make_movement("b", **overrides)]
    )


def test_same_total_value_alone_is_not_a_duplicate(make_movement):
    left = make_movement("a")
    right = replace(make_movement("b"), description="Feijão", supplier_id="456")
    assert not find_duplicate_movements([left, right])


def test_duplicate_requires_same_quantity_unit_and_date(make_movement):
    original = make_movement("a")
    variants = [
        replace(make_movement("b"), quantity=Decimal(20)),
        replace(make_movement("c"), unit="pacote"),
        replace(make_movement("d"), event_date=date(2025, 2, 10)),
    ]
    assert not find_duplicate_movements([original, *variants])


def test_repeated_id_is_separately_identified(make_movement):
    finding = find_duplicate_movements([make_movement("same"), make_movement("same")])[0]
    assert finding.criteria["kind"] == "repeated_identifier_candidate"
    assert finding.evidence["matched_fields"] == ["id"]
    assert "não garante ID globalmente único" in finding.limitations[0]


def test_outlier_above_threshold_reports_exact_median_and_percent(make_movement):
    rows = [make_movement("r1", "10"), make_movement("r2", "10"),
            make_movement("r3", "10"), make_movement("target", "16")]
    result = next(f for f in find_outlier_prices(rows) if f.movement_id == "target")
    assert result.alert_type == "alert"
    assert Decimal(result.evidence["reference_median"]) == Decimal(10)
    assert Decimal(result.evidence["threshold"]) == Decimal(15)
    assert Decimal(result.evidence["divergence_percent"]) == Decimal(60)
    assert result.evidence["reference_count"] == 3
    assert set(result.evidence["reference_ids"]) == {"r1", "r2", "r3"}
    assert "não prova de fraude" in result.explanation


@pytest.mark.parametrize("price", ["9", "10", "15"])
def test_price_below_equal_or_at_threshold_does_not_alert(make_movement, price):
    rows = [make_movement("r1", "10"), make_movement("r2", "10"),
            make_movement("r3", "10"), make_movement("target", price)]
    assert not [finding for finding in find_outlier_prices(rows)
                if finding.movement_id == "target" and finding.alert_type == "alert"]


def test_median_for_even_references_is_exact_decimal(make_movement):
    rows = [make_movement("r1", "10"), make_movement("r2", "11"),
            make_movement("r3", "12"), make_movement("r4", "13"),
            make_movement("target", "20")]
    result = next(f for f in find_outlier_prices(rows) if f.movement_id == "target")
    assert Decimal(result.evidence["reference_median"]) == Decimal("11.5")


@pytest.mark.parametrize(
    "overrides",
    [
        {"unit": "pacote"},
        {"category": "Outro"},
        {"description": "Arroz tipo 2"},
        {"event_date": date(2025, 2, 10)},
        {"event_date": date(2026, 4, 10)},
        {"municipality": "São Paulo", "state": "SP"},
    ],
)
def test_incomparable_prices_do_not_form_reference_group(make_movement, overrides):
    target = make_movement("target", "100")
    peers = [make_movement(f"r{i}", **overrides) for i in range(3)]
    result = next(f for f in find_outlier_prices([target, *peers])
                  if f.movement_id == "target")
    assert result.alert_type == "insufficient_evidence"
    assert result.evidence["reference_count"] == 0


def test_fewer_than_three_external_references_is_explicitly_insufficient(make_movement):
    rows = [make_movement("r1"), make_movement("r2"), make_movement("target", "100")]
    result = next(f for f in find_outlier_prices(rows) if f.movement_id == "target")
    assert result.alert_type == "insufficient_evidence"
    assert result.evidence["reference_count"] == 2


def test_repeated_reference_ids_do_not_inflate_sample_count(make_movement):
    rows = [make_movement("r1"), make_movement("r1"),
            make_movement("r2"), make_movement("target", "100")]
    result = next(f for f in find_outlier_prices(rows) if f.movement_id == "target")
    assert result.alert_type == "insufficient_evidence"
    assert result.evidence["reference_count"] == 1


def test_multiplier_is_configurable_and_reported(make_movement):
    rows = [make_movement("r1", "10"), make_movement("r2", "10"),
            make_movement("r3", "10"), make_movement("target", "25")]
    result = next(f for f in find_outlier_prices(rows, Decimal(2))
                  if f.movement_id == "target")
    assert result.alert_type == "alert"
    assert result.criteria["multiplier"] == "2"


@pytest.mark.parametrize("price", [Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_invalid_unit_prices_are_never_comparisons(make_movement, price):
    rows = [make_movement(f"r{i}") for i in range(3)]
    rows.append(make_movement("invalid", price))
    assert not [f for f in find_outlier_prices(rows) if f.movement_id == "invalid"]


@pytest.mark.parametrize("multiplier", [Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_price_multiplier_must_be_finite_and_positive(make_movement, multiplier):
    with pytest.raises(ValueError, match="multiplier"):
        find_outlier_prices([make_movement("one")], multiplier)


def test_missing_required_fields_are_named_and_optional_empty_values_are_ignored(make_movement):
    original = make_movement("x")
    assert not find_missing_required_data([replace(original, source_url=None)])
    location_missing = find_missing_required_data(
        [replace(original, source_url=None, municipality=None, state=None)]
    )[0]
    assert "source_url" not in location_missing.evidence["missing_fields"]
    assert "municipality (comparabilidade de preço)" in location_missing.evidence["missing_fields"]
    finding = find_missing_required_data(
        [replace(original, description=None, unit_price=None, source_url=None)]
    )[0]
    assert "description (comparação de produto/duplicidade)" in finding.evidence["missing_fields"]
    assert "unit_price (preço)" in finding.evidence["missing_fields"]


def test_wrongly_typed_date_is_reported_without_crashing(make_movement):
    row = replace(make_movement("x"), event_date="2026-02-10")
    findings = run_all_rules([row])
    missing = next(f for f in findings if f.rule_id == "required_data")
    assert "event_date (duplicidade/preço)" in missing.evidence["missing_fields"]


def test_invalid_and_multiple_fields_are_separated(make_movement):
    row = replace(
        make_movement("x"), description=" ", supplier_name=None, supplier_id=None,
        unit=None, unit_price=Decimal("NaN"), total_value=Decimal(-1), quantity=None,
    )
    finding = find_missing_required_data([row])[0]
    assert "supplier_id ou supplier_name (duplicidade)" in finding.evidence["missing_fields"]
    assert "unit_price (deve ser finito e maior que zero)" in finding.evidence["invalid_fields"]
    assert "total_value (deve ser finito e não negativo)" in finding.evidence["invalid_fields"]


def test_run_all_rules_handles_empty_and_incomplete_records(make_movement):
    assert run_all_rules([]) == []
    incomplete = replace(
        make_movement("incomplete", description=None,
                      supplier_name=None, supplier_id=None),
        unit_price=None,
    )
    findings = run_all_rules([incomplete])
    assert all(f.movement_id == "incomplete" for f in findings)
    assert all(f.rule_id and f.alert_type in {"alert", "insufficient_evidence"}
               for f in findings)
    missing = next(f for f in findings if f.rule_id == "required_data")
    assert missing.evidence["missing_fields"]


def test_demo_still_exercises_three_rules_with_traceable_findings():
    findings = run_all_rules(sample_movements())
    assert {finding.rule for finding in findings if finding.alert_type == "alert"} == {
        "Possível duplicidade", "Valor fora do critério", "Informação obrigatória ausente"
    }
    assert all(finding.movement_id and finding.rule_id and finding.explanation
               and isinstance(finding.evidence, dict) for finding in findings)
>>>>>>> Stashed changes
