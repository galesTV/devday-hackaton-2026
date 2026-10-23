from datetime import date
from decimal import Decimal

from .domain import FoodMovement, Source


def movement(
    id: str,
    description: str | None,
    price: str | None,
    total: str | None,
    supplier: str | None = "Cooperativa Verde",
    source: Source = Source.PNCP,
) -> FoodMovement:
    return FoodMovement(
        id=id,
        source=source,
        description=description,
        category="Alimentos",
        supplier_id="123" if supplier else None,
        supplier_name=supplier,
        buyer_name="Prefeitura Exemplo",
        municipality="Brasília",
        state="DF",
        event_date=date(2026, 10, 20),
        quantity=Decimal(100) if price else None,
        unit="kg" if price else None,
        unit_price=Decimal(price) if price else None,
        total_value=Decimal(total) if total else None,
        source_url=None,
    )


def sample_movements() -> list[FoodMovement]:
    return [
        movement("pncp-001", "Tomate italiano", "8.00", "800.00"),
        movement("pncp-002", "Tomate italiano", "8.00", "800.00"),  # duplicidade
        movement("compras-001", "Tomate italiano", "7.50", "750.00", source=Source.COMPRAS_GOV),
        movement("compras-002", "Tomate italiano", "7.80", "780.00", source=Source.COMPRAS_GOV),
        movement("pncp-003", "Tomate italiano", "18.00", "1800.00"),  # valor atípico
        movement("trans-001", None, None, "30000.00", supplier=None, source=Source.TRANSPARENCIA),  # obrigatório ausente
    ]
