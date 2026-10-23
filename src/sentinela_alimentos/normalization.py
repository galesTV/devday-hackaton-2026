"""Adapta os campos das fontes para uma mesma leitura; o bruto continua rastreável."""

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .domain import FoodMovement, Source


def normalized_text(value: str | None) -> str:
    if not value:
        return ""
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain.lower()).strip()


def decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def from_pncp(item: dict[str, Any]) -> FoodMovement:
    """Normaliza item de contratação PNCP; os nomes podem variar por versão."""
    quantity = decimal(item.get("quantidade") or item.get("quantidadeItem"))
    unit_price = decimal(item.get("valorUnitarioEstimado") or item.get("valorUnitario"))
    return FoodMovement(
        id=f"pncp:{item.get('numeroItem') or item.get('id')}",
        source=Source.PNCP,
        description=item.get("descricao") or item.get("descricaoItem"),
        category=item.get("categoria") or "Alimentos",
        supplier_id=item.get("niFornecedor"),
        supplier_name=item.get("nomeFornecedor"),
        buyer_name=item.get("nomeOrgao"),
        municipality=item.get("municipio"), state=item.get("uf"),
        event_date=iso_date(item.get("dataInclusao")), quantity=quantity,
        unit=item.get("unidadeMedida"), unit_price=unit_price,
        total_value=decimal(item.get("valorTotal")) or (
            quantity * unit_price if quantity is not None and unit_price is not None else None
        ), source_url=item.get("url"), raw=item,
    )


def from_compras_gov(item: dict[str, Any]) -> FoodMovement:
    """Normaliza retorno de preços praticados/CATMAT da API Compras.gov.br."""
    quantity = decimal(item.get("quantidade"))
    unit_price = decimal(item.get("valorUnitario") or item.get("precoUnitario"))
    return FoodMovement(
        id=f"compras:{item.get('idCompra') or item.get('codigoItem')}",
        source=Source.COMPRAS_GOV,
        description=item.get("descricaoMaterial") or item.get("descricao"),
        category=item.get("grupoMaterial") or "Alimentos",
        supplier_id=item.get("cnpjFornecedor"), supplier_name=item.get("nomeFornecedor"),
        buyer_name=item.get("nomeUasg") or item.get("orgao"),
        municipality=item.get("municipio"), state=item.get("uf"),
        event_date=iso_date(item.get("dataCompra")), quantity=quantity,
        unit=item.get("unidadeFornecimento"), unit_price=unit_price,
        total_value=decimal(item.get("valorTotal")) or (
            quantity * unit_price if quantity is not None and unit_price is not None else None
        ), source_url=item.get("url"), raw=item,
    )


def from_transparency(item: dict[str, Any]) -> FoodMovement:
    """Normaliza convênios/transferências como contexto de financiamento."""
    return FoodMovement(
        id=f"transparencia:{item.get('id') or item.get('numero')}",
        source=Source.TRANSPARENCIA,
        description=item.get("objeto") or item.get("descricao"),
        category="Transferência para alimentação" if "aliment" in normalized_text(item.get("objeto")) else None,
        supplier_id=item.get("cnpjBeneficiario"), supplier_name=item.get("nomeBeneficiario"),
        buyer_name=item.get("nomeOrgaoConcedente"), municipality=item.get("municipio"),
        state=item.get("uf"), event_date=iso_date(item.get("dataInicioVigencia")),
        quantity=None, unit=None, unit_price=None,
        total_value=decimal(item.get("valorLiberado") or item.get("valorGlobal")),
        source_url=item.get("url"), raw=item,
    )
