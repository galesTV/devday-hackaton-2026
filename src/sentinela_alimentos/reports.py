"""Deterministic citizen reports and a dependency-free, text-only PDF exporter."""

from datetime import datetime
from html import escape

from .domain import Finding, FoodMovement


def build_report(
    movement: FoodMovement,
    findings: list[Finding],
    observations: str = "",
    *,
    simulated: bool = False,
) -> dict[str, str]:
    """Build the preview from the exact movement and findings shown by the app."""
    generated = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %Z")
    source = f"<{movement.source_url}>" if movement.source_url else "Link de origem não fornecido pela fonte consultada."
    source_label = (
        f"Demonstração simulada (registro fictício; rótulo no fixture: {movement.source})"
        if simulated
        else str(movement.source)
    )
    unit_price = f"R$ {movement.unit_price:.2f}" if movement.unit_price is not None else "Indisponível"
    total = f"R$ {movement.total_value:.2f}" if movement.total_value is not None else "Indisponível"
    alert_lines = [f"- {finding.rule}: {finding.explanation}" for finding in findings] or ["- Nenhum alerta associado a este registro."]
    lines = [
        "# Relatório informativo de compra pública",
        f"Gerado em: {generated}",
        "",
        "## Identificação",
        f"- Registro: {movement.id}", f"- Fonte: {source_label}", f"- Órgão: {movement.buyer_name or 'Não informado'}",
        f"- Fornecedor: {movement.supplier_name or 'Não informado'}", f"- Município/UF: {movement.municipality or 'Não informado'} / {movement.state or '—'}",
        f"- Data: {movement.event_date or 'Não informada'}", f"- Item: {movement.description or 'Descrição ausente'}",
        f"- Quantidade/unidade: {movement.quantity if movement.quantity is not None else 'Não informada'} {movement.unit or ''}",
        f"- Preço unitário: {unit_price}", f"- Valor total: {total}",
        "", "## Alertas", *alert_lines,
        "", "## Metodologia", "Foram usados os alertas já calculados e exibidos no painel. O critério estatístico e as referências aparecem na explicação de cada alerta quando disponíveis; nenhum preço ou referência adicional foi calculado para este relatório.",
        "", "## Evidências e origem", source,
        "", "## Possíveis explicações a verificar", "Diferenças de especificação, embalagem, qualidade, quantidade, frete, local e data podem explicar valores distintos. Confirme esses fatores nos documentos originais.",
        "", "## Limitações", "Este relatório depende dos campos disponibilizados pela fonte e das regras determinísticas do painel. Ausência de alerta não comprova regularidade; um alerta não comprova fraude ou superfaturamento.",
        "", "## Conclusão informativa", "O registro merece a revisão indicada acima, considerando as evidências e limitações descritas. Nenhuma denúncia foi enviada.",
        "", "## Observações complementares do cidadão", observations.strip() or "(Nenhuma observação adicionada.)",
    ]
    text = "\n".join(lines)
    html = "<article>" + "<pre>" + escape(text) + "</pre></article>"
    return {"text": text, "html": html, "generated_at": generated}


def export_pdf(report: dict[str, str]) -> bytes:
    """Export the preview as a compact PDF using built-in PDF primitives."""
    content_lines = []
    for line in report["text"].splitlines():
        plain = line
        chunks = [plain[i:i + 92] for i in range(0, max(len(plain), 1), 92)]
        content_lines.extend(chunks)
    pages = [content_lines[i:i + 48] for i in range(0, len(content_lines), 48)] or [[]]
    objects: list[bytes] = []
    page_ids = [4 + 2 * index for index in range(len(pages))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append((f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(pages)} >>").encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for index, lines in enumerate(pages):
        page_id = 4 + 2 * index
        stream_id = page_id + 1
        commands = ["BT", "/F1 9 Tf", "48 800 Td", "12 TL"]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.extend([f"({safe}) Tj", "T*"])
        commands.append("ET")
        stream = "\n".join(commands).encode("cp1252", "replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(result)
