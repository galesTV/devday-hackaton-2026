from dataclasses import replace
from datetime import date

from sentinela_alimentos import collection
from sentinela_alimentos.collection import (
    MAX_RECORDS,
    collect_food_data,
    deduplicate_movements,
)
from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.domain import Source


def test_deduplication_keeps_provenance_and_never_merges_sources():
    original = sample_movements()[0]
    repeated = replace(original)
    same_identifier_other_source = replace(original, source=Source.COMPRAS_GOV)

    unique, removed = deduplicate_movements(
        [original, repeated, same_identifier_other_source]
    )

    assert removed == 1
    assert unique == [original, same_identifier_other_source]


def test_demo_data_stays_within_the_supported_review_limit():
    assert len(sample_movements()) <= MAX_RECORDS


def test_collection_keeps_other_sources_when_one_source_fails(monkeypatch):
    rows = sample_movements()[:1]

    def failing_pncp(*_args):
        raise ValueError("fonte indisponível")

    monkeypatch.setattr(collection, "pncp_food_movements", failing_pncp)
    monkeypatch.setattr(collection, "compras_food_catalog", lambda *_args: rows)
    monkeypatch.setattr(collection, "transparency_food_agreements", lambda *_args: [])
    monkeypatch.setattr(collection, "compras_regional_market_prices", lambda *_args: [])

    result = collect_food_data("arroz", date(2026, 10, 1), date(2026, 10, 2), "DF")

    assert result.movements == rows
    assert result.errors == ["PNCP: fonte indisponível"]
