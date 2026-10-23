from dataclasses import replace

from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.reports import build_report, export_pdf
from sentinela_alimentos.rules import run_all_rules


def test_report_contains_selected_record_and_existing_findings():
    item = sample_movements()[0]
    findings = [finding for finding in run_all_rules(sample_movements()) if finding.movement_id == item.id]
    report = build_report(item, findings, observations="Verificar nota fiscal")

    assert item.id in report["text"]
    assert item.source.value in report["text"]
    assert "Verificar nota fiscal" in report["text"]
    assert all(finding.explanation in report["text"] for finding in findings)
    assert "não comprova fraude" in report["text"]


def test_export_pdf_returns_valid_pdf_with_preview_content():
    report = build_report(sample_movements()[0], [], observations="Anotação")
    pdf = export_pdf(report)

    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.endswith(b"%%EOF")
    assert "Anotação".encode("cp1252") in pdf


def test_report_preserves_supplied_source_link_and_does_not_invent_one():
    item = sample_movements()[0]
    linked = build_report(replace(item, source_url="https://pncp.gov.br/consulta/registro"), [])
    unlinked = build_report(item, [])

    assert "https://pncp.gov.br/consulta/registro" in linked["text"]
    assert "Link de origem não fornecido" in unlinked["text"]
    assert "https://" not in unlinked["text"]


def test_simulated_report_does_not_present_fixture_source_as_official():
    item = sample_movements()[0]
    report = build_report(item, [], simulated=True)

    assert "Demonstração simulada" in report["text"]
    assert "fixture: PNCP" in report["text"]


def test_ai_summary_is_separate_from_facts_and_marked_as_interpretation():
    report = build_report(
        sample_movements()[0], [], ai_summary="Interpretação gerada pelo modelo."
    )

    assert "## Evidências e origem" in report["text"]
    assert "## Análise assistida por IA (interpretação, não evidência)" in report["text"]
    assert report["text"].index("## Evidências e origem") < report["text"].index("## Análise assistida por IA")
    assert "Interpretação gerada pelo modelo." in report["text"]


def test_pdf_preserves_portuguese_text_and_paginates_long_reports():
    item = sample_movements()[0]
    report = build_report(item, [], observations="São informações para revisão cidadã. " * 200)
    pdf = export_pdf(report)

    assert "São informações".encode("cp1252") in pdf
    assert b"/Count 2" in pdf or b"/Count 3" in pdf or b"/Count 4" in pdf

