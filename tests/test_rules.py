from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.rules import run_all_rules


def test_demo_exercises_the_three_required_rules():
    rules = {finding.rule for finding in run_all_rules(sample_movements())}
    assert rules == {"Possível duplicidade", "Valor fora do critério", "Informação obrigatória ausente"}


def test_findings_are_explainable():
    findings = run_all_rules(sample_movements())
    assert all(finding.explanation for finding in findings)
