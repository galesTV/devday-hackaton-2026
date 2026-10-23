from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from sentinela_alimentos.demo_data import movement, sample_movements
from sentinela_alimentos.rules import (
    find_duplicate_movements,
    find_missing_required_data,
    find_outlier_prices,
    run_all_rules,
)


@pytest.fixture
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
