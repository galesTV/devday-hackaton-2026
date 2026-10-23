from sentinela_alimentos.domain import Source
from sentinela_alimentos.normalization import (
    from_compras_gov,
    from_pncp,
    from_transparency,
)


def test_pncp_normalization_preserves_identifiers_organs_and_prices():
    movement = from_pncp(
        {
            "numeroItem": 12,
            "descricaoItem": "ARROZ BENEFICIADO",
            "quantidade": 100,
            "valorUnitarioEstimado": 8.5,
            "nomeOrgao": "Prefeitura de Exemplo",
            "nomeFornecedor": "Cooperativa Local",
            "niFornecedor": "12345678000199",
            "municipio": "Brasília",
            "uf": "DF",
            "dataInclusao": "2026-10-23T10:00:00",
            "unidadeMedida": "kg",
            "url": "https://pncp.gov.br/app/editais/exemplo",
        }
    )
    assert movement.source is Source.PNCP
    assert movement.id == "pncp:12"
    assert str(movement.total_value) == "850.0"
    assert movement.supplier_id == "12345678000199"
    assert movement.source_url.endswith("exemplo")


def test_other_sources_normalize_to_the_same_food_movement_model():
    compras = from_compras_gov(
        {"codigoItem": 123, "descricaoMaterial": "FEIJÃO", "precoUnitario": 9}
    )
    transparency = from_transparency(
        {"id": 456, "objeto": "Aquisição de alimentos", "valorGlobal": 1000}
    )
    assert compras.source is Source.COMPRAS_GOV
    assert transparency.source is Source.TRANSPARENCIA
    assert compras.id == "compras:123"
    assert transparency.id == "transparencia:456"
