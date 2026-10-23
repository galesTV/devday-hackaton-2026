"""Consultas reais, limitadas e explícitas para a apresentação do hackathon."""

import os
from datetime import date
from pathlib import Path

import httpx

from .clients import ComprasGovClient, PNCPClient, TransparencyClient
from .domain import FoodMovement, Source
from .normalization import decimal, iso_date, normalized_text

FOOD_TERMS = (
    "aliment",
    "arroz",
    "feij",
    "leite",
    "fruta",
    "verdura",
    "legume",
    "carne",
    "merenda",
    "hortifruti",
    "genero",
    "refeicao",
    "cesta basica",
    "panific",
)

FOOD_CLASSES = {
    8905: ("carne", "frango", "peixe"),
    8910: ("leite", "queijo", "ovo"),
    8915: ("tomate", "fruta", "verdura", "legume", "batata"),
    8920: ("arroz", "feij", "farinha", "macarrao", "cereal"),
    8945: ("oleo", "azeite"),
}


def is_food(value: str | None) -> bool:
    text = normalized_text(value)
    return any(term in text for term in FOOD_TERMS)


def food_class_for(query: str) -> int | None:
    normalized_query = normalized_text(query)
    for code, terms in FOOD_CLASSES.items():
        if any(term in normalized_query for term in terms):
            return code
    return None


def transparency_api_key() -> str:
    """Read the key from the environment or a local .env file without logging it."""
    if key := os.getenv("TRANSPARENCIA_API_KEY"):
        return key
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if name.strip() == "TRANSPARENCIA_API_KEY" and separator:
                return value.strip().strip('"').strip("'")
    return ""


def pncp_food_movements(
    start: date, end: date, query: str | None = None, max_purchases: int = 10
) -> list[FoodMovement]:
    """PNCP does not expose a keyword filter; filter publication objects locally."""
    client = PNCPClient()
    try:
        food_purchases: list[dict] = []
        for page in range(1, 6):
            publications = client.publications(start.isoformat(), end.isoformat(), page=page)
            food_purchases.extend(
                record for record in publications if is_food(record.get("objetoCompra"))
            )
            if len(food_purchases) >= max_purchases:
                break
        movements: list[FoodMovement] = []
        for purchase in food_purchases[:max_purchases]:
            organization = purchase.get("orgaoEntidade") or {}
            try:
                items = client.purchase_items(
                    organization["cnpj"],
                    purchase["anoCompra"],
                    purchase["sequencialCompra"],
                )
            except (httpx.HTTPError, KeyError):
                # A publication may exist before its items are available in PNCP.
                # Keep the source record, clearly without a unit-price comparison.
                movements.append(
                    FoodMovement(
                        id=f"pncp:{purchase['numeroControlePNCP']}",
                        source=Source.PNCP,
                        description=purchase.get("objetoCompra"),
                        category="Alimentos",
                        supplier_id=None,
                        supplier_name=None,
                        buyer_name=organization.get("razaoSocial"),
                        municipality=(purchase.get("unidadeOrgao") or {}).get("municipioNome"),
                        state=(purchase.get("unidadeOrgao") or {}).get("ufSigla"),
                        event_date=iso_date(purchase.get("dataPublicacaoPncp")),
                        quantity=None,
                        unit=None,
                        unit_price=None,
                        total_value=decimal(purchase.get("valorTotalHomologado"))
                        or decimal(purchase.get("valorTotalEstimado")),
                        municipality_code=str(
                            (purchase.get("unidadeOrgao") or {}).get("codigoIbge") or ""
                        )
                        or None,
                        source_url="https://pncp.gov.br/app/editais/"
                        + purchase["numeroControlePNCP"],
                        raw={"purchase": purchase},
                    )
                )
                continue
            for item in items:
                description = item.get("descricao") or item.get("descricaoItem")
                if not is_food(description) or (
                    query and normalized_text(query) not in normalized_text(description)
                ):
                    continue
                quantity = decimal(item.get("quantidade"))
                unit_price = decimal(
                    item.get("valorUnitarioHomologado")
                    or item.get("valorUnitarioEstimado")
                )
                movements.append(
                    FoodMovement(
                        id=f"pncp:{purchase['numeroControlePNCP']}:{item.get('numeroItem')}",
                        source=Source.PNCP,
                        description=description,
                        category="Alimentos",
                        supplier_id=item.get("niFornecedor"),
                        supplier_name=item.get("nomeFornecedor"),
                        buyer_name=organization.get("razaoSocial"),
                        municipality=(purchase.get("unidadeOrgao") or {}).get("municipioNome"),
                        state=(purchase.get("unidadeOrgao") or {}).get("ufSigla"),
                        event_date=iso_date(purchase.get("dataPublicacaoPncp")),
                        quantity=quantity,
                        unit=item.get("unidadeMedida"),
                        unit_price=unit_price,
                        total_value=decimal(item.get("valorTotalHomologado"))
                        or (quantity * unit_price if quantity and unit_price else None),
                        municipality_code=str(
                            (purchase.get("unidadeOrgao") or {}).get("codigoIbge") or ""
                        )
                        or None,
                        source_url="https://pncp.gov.br/app/editais/" + purchase["numeroControlePNCP"],
                        raw={"purchase": purchase, "item": item},
                    )
                )
        return movements
    finally:
        client.close()


def compras_food_catalog(query: str) -> list[FoodMovement]:
    """Search the first CATMAT food-catalog page; prices are queried per chosen item."""
    client = ComprasGovClient()
    try:
        catalog = client.food_catalog(class_code=food_class_for(query))
        selected = [item for item in catalog if normalized_text(query) in normalized_text(item.get("descricaoItem"))]
        return [
            FoodMovement(
                id=f"compras-catalogo:{item['codigoItem']}",
                source=Source.COMPRAS_GOV,
                description=item.get("descricaoItem"),
                category=item.get("nomeClasse"),
                supplier_id=None,
                supplier_name=None,
                buyer_name="Catálogo CATMAT",
                municipality=None,
                state=None,
                event_date=iso_date(item.get("dataHoraAtualizacao")),
                quantity=None,
                unit=None,
                unit_price=None,
                total_value=None,
                source_url="https://dadosabertos.compras.gov.br/swagger-ui/index.html",
                raw=item,
            )
            for item in selected[:20]
        ]
    finally:
        client.close()


def compras_regional_market_prices(
    query: str, state: str | None, municipality_code: str | None
) -> list[FoodMovement]:
    """Fetch public price samples for the CATMAT food item in the purchase region."""
    client = ComprasGovClient()
    try:
        catalog = client.food_catalog(class_code=food_class_for(query))
        matches = [
            item
            for item in catalog
            if normalized_text(query) in normalized_text(item.get("descricaoItem"))
        ]
        movements: list[FoodMovement] = []
        for catalog_item in matches[:3]:
            records = client.prices_for_catalog_item(
                catalog_item["codigoItem"],
                state=state,
                municipality_code=municipality_code,
            )
            if not records and municipality_code:
                # Keep the geographic criterion, widening only from city to UF.
                records = client.prices_for_catalog_item(
                    catalog_item["codigoItem"], state=state
                )
            for record in records:
                price = decimal(
                    record.get("valorUnitario")
                    or record.get("precoUnitario")
                    or record.get("valorUnitarioHomologado")
                )
                if price is None:
                    continue
                movements.append(
                    FoodMovement(
                        id=f"compras-preco:{catalog_item['codigoItem']}:{record.get('idCompra') or len(movements)}",
                        source=Source.COMPRAS_GOV,
                        description=catalog_item.get("descricaoItem"),
                        category=catalog_item.get("nomeClasse"),
                        supplier_id=record.get("cnpjFornecedor"),
                        supplier_name=record.get("nomeFornecedor"),
                        buyer_name=record.get("nomeUasg") or record.get("nomeOrgao"),
                        municipality=record.get("municipio"),
                        state=record.get("uf") or state,
                        event_date=iso_date(record.get("dataCompra")),
                        quantity=decimal(record.get("quantidade")),
                        unit=record.get("unidadeFornecimento"),
                        unit_price=price,
                        total_value=decimal(record.get("valorTotal")),
                        municipality_code=str(record.get("codigoMunicipio") or municipality_code or "") or None,
                        source_url="https://dadosabertos.compras.gov.br/swagger-ui/index.html",
                        raw={"catalog": catalog_item, "price": record},
                    )
                )
        return movements
    finally:
        client.close()


def transparency_food_agreements(start: date, end: date) -> list[FoodMovement]:
    """The API has no food term filter: retrieve a period and filter the object locally."""
    if (end - start).days > 31:
        raise ValueError(
            "O Portal da Transparência aceita consulta de convênios por período de até 1 mês."
        )
    client = TransparencyClient(transparency_api_key())
    try:
        records = client.agreements(
            {
                "dataInicial": start.strftime("%d/%m/%Y"),
                "dataFinal": end.strftime("%d/%m/%Y"),
                "pagina": 1,
            }
        )
        return [
            FoodMovement(
                id=f"transparencia:{record.get('id') or record.get('numero')}",
                source=Source.TRANSPARENCIA,
                description=record.get("objeto"),
                category="Transferência para alimentação",
                supplier_id=record.get("cnpjConvenente"),
                supplier_name=record.get("nomeConvenente"),
                buyer_name=record.get("nomeOrgao"),
                municipality=record.get("municipio"),
                state=record.get("uf"),
                event_date=iso_date(record.get("dataInicioVigencia")),
                quantity=None,
                unit=None,
                unit_price=None,
                total_value=decimal(record.get("valorLiberado"))
                or decimal(record.get("valorGlobal")),
                source_url="https://portaldatransparencia.gov.br/transferencias",
                raw=record,
            )
            for record in records
            if is_food(record.get("objeto"))
        ]
    finally:
        client.close()
