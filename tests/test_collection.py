from dataclasses import replace

from sentinela_alimentos.collection import MAX_RECORDS, deduplicate_movements
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
