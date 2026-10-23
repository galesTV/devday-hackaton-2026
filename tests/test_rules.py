from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.rules import (
    find_regional_price_discrepancies,
    run_all_rules,
)


def test_demo_exercises_the_three_required_rules():
    rules = {finding.rule for finding in run_all_rules(sample_movements())}
    assert rules == {"Possível duplicidade", "Valor fora do critério", "Informação obrigatória ausente"}


def test_findings_are_explainable():
    findings = run_all_rules(sample_movements())
    assert all(finding.explanation for finding in findings)


def test_regional_comparison_uses_total_divided_by_quantity_when_needed():
    purchase, *_, reference = sample_movements()
    purchase = purchase.__class__(
        **{
            **{field: getattr(purchase, field) for field in purchase.__dataclass_fields__},
            "unit_price": None,
            "total_value": 1500,
            "quantity": 100,
            "state": "DF",
            "municipality_code": "5300108",
        }
    )
    reference = reference.__class__(
        **{
            **{field: getattr(reference, field) for field in reference.__dataclass_fields__},
            "unit_price": 8,
            "state": "DF",
            "municipality_code": "5300108",
        }
    )
    findings = find_regional_price_discrepancies([purchase], [reference])
    assert findings[0].rule == "Possível discrepância regional de preço"
