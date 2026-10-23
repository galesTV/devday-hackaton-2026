"""Modelo canônico que permite ler fontes públicas distintas lado a lado."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Source(StrEnum):
    PNCP = "PNCP"
    COMPRAS_GOV = "Compras.gov.br"
    TRANSPARENCIA = "Portal da Transparência"


class ReviewStatus(StrEnum):
    PENDING = "Pendente"
    REVIEWED = "Revisada"


@dataclass(frozen=True, slots=True)
class FoodMovement:
    id: str
    source: Source
    description: str | None
    category: str | None
    supplier_id: str | None
    supplier_name: str | None
    buyer_name: str | None
    municipality: str | None
    state: str | None
    event_date: date | None
    quantity: Decimal | None
    unit: str | None
    unit_price: Decimal | None
    total_value: Decimal | None
    source_url: str | None = None
    raw: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True, slots=True)
class Finding:
    movement_id: str
    rule: str
    explanation: str
    severity: str
    rule_id: str = ""
    alert_type: str = "alert"
    criteria: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
