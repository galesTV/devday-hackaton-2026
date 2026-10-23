from collections import defaultdict
from datetime import date, timedelta

import streamlit as st

from sentinela_alimentos.collection import collect_food_data
from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.reports import build_report, export_pdf
from sentinela_alimentos.rules import run_all_rules
from sentinela_alimentos.session_state import public_movements, save_public_result

st.set_page_config(page_title="Sentinela Alimentos", page_icon="🌾", layout="wide")
st.title("🌾 Sentinela Alimentos")
st.caption("Conferência explicável de compras públicas. Um alerta pede revisão; não conclui fraude.")

if "review_status" not in st.session_state:
    st.session_state.review_status = {}
if "live_result" not in st.session_state:
    st.session_state.live_result = None
if "live_search_completed" not in st.session_state:
    st.session_state.live_search_completed = False

mode = st.sidebar.radio("Dados", ["Demonstração simulada", "Consultar fontes oficiais"])
is_demo = mode == "Demonstração simulada"
result = st.session_state.live_result
movements = sample_movements() if is_demo else public_movements(st.session_state)
if is_demo:
    st.info("Demonstração simulada — estes registros são fictícios e não representam compras oficiais.")

if mode == "Consultar fontes oficiais":
    st.sidebar.caption("Dados reais consultados nas fontes indicadas. Portal da Transparência requer TRANSPARENCIA_API_KEY.")
    product = st.sidebar.text_input("Produto alimentar", value="arroz")
    state = st.sidebar.selectbox(
        "UF",
        [
            "Todas", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
            "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS",
            "RO", "RR", "SC", "SP", "SE", "TO",
        ],
    )
    start = st.sidebar.date_input("Data inicial", value=date.today() - timedelta(days=30))
    end = st.sidebar.date_input("Data final", value=date.today())
    if st.sidebar.button("Buscar dados públicos", type="primary"):
        save_public_result(st.session_state, collect_food_data(
            product, start, end, None if state == "Todas" else state
        ))
        st.rerun()
    result = st.session_state.live_result
    movements = result.movements if result else []
    if result:
        for error in result.errors:
            st.warning(error)
        if result.duplicates_removed:
            st.caption(f"{result.duplicates_removed} registro(s) repetido(s) removido(s) na coleta.")
        if result.truncated:
            st.caption("A visualização foi limitada aos primeiros 100 registros únicos.")
    if not movements:
        if st.session_state.live_search_completed:
            st.info("A consulta terminou sem registros utilizáveis. Tente outros filtros ou verifique as mensagens das fontes.")
        else:
            st.info("Sem consulta carregada. Defina os filtros e clique em Buscar dados públicos.")
    else:
        st.caption("Registros reais retornados pelas fontes oficiais; preços CATMAT podem compor referências comparáveis nas regras de preço.")

findings = run_all_rules(movements)
grouped = defaultdict(list)
by_id = {item.id: item for item in movements if item.id}
for finding in findings:
    grouped[finding.movement_id].append(finding)


def status_key(item_id: str, source: str) -> str:
    return f"{source}:{item_id}"


def occurrence_status(item_id: str, source: str) -> str:
    """Use the widget value first, so a click moves the occurrence on this rerun."""
    key = status_key(item_id, source)
    status = st.session_state.get(f"status-{key}")
    if status not in {"Pendente", "Revisada"}:
        status = st.session_state.review_status.get(key, "Pendente")
    st.session_state.review_status[key] = status
    return status


total = sum(finding.alert_type == "alert" for finding in findings)
reviewed = sum(
    occurrence_status(item.id, str(item.source)) == "Revisada"
    for item in movements
    if item.id
)
one, two, three = st.columns(3)
one.metric("Registros demonstrados", len(movements))
two.metric("Ocorrências sinalizadas", total)
three.metric("Revisadas", reviewed)

st.subheader("Ocorrências para revisão")
if movements and not findings:
    st.success("Nenhuma ocorrência foi sinalizada pelas regras aplicadas aos registros retornados.")


def show_occurrence(item_id: str, record_findings: list) -> None:
    item = by_id.get(item_id)
    if item is None:
        st.info("Registro sem identificador rastreável")
        for finding in record_findings:
            display = st.info if finding.alert_type == "insufficient_evidence" else st.warning
            display(f"**{finding.rule}** — {finding.explanation}")
        return
    review_key = status_key(item_id, str(item.source))
    with st.expander(
        f"{item_id} · {item.source} · {item.description or 'Descrição ausente'}",
        expanded=True,
    ):
        for finding in record_findings:
            display = st.info if finding.alert_type == "insufficient_evidence" else st.warning
            display(f"**{finding.rule}** — {finding.explanation}")
        c1, c2, c3 = st.columns(3)
        c1.write(
            f"Valor: R$ {item.total_value:.2f}"
            if item.total_value is not None
            else "Valor: indisponível"
        )
        c2.write(f"Fornecedor: {item.supplier_name or 'não informado'}")
        status = c3.radio(
            "Status",
            ["Pendente", "Revisada"],
            index=1 if occurrence_status(item_id, str(item.source)) == "Revisada" else 0,
            key=f"status-{review_key}",
            horizontal=True,
        )
        st.session_state.review_status[review_key] = status
        if item.source_url:
            st.link_button("Abrir registro ou fonte oficial", item.source_url)
        report = build_report(item, record_findings, simulated=is_demo)
        st.download_button(
            "Baixar relatório PDF",
            data=export_pdf(report),
            file_name=f"sentinela-{item.source}-{item_id}.pdf".replace("/", "-"),
            mime="application/pdf",
            key=f"report-{review_key}",
        )


pending_items = []
reviewed_items = []
unidentified_items = []
for movement_id, record_findings in grouped.items():
    item = by_id.get(movement_id)
    if item is None:
        unidentified_items.append((movement_id, record_findings))
    elif occurrence_status(movement_id, str(item.source)) == "Revisada":
        reviewed_items.append((movement_id, record_findings))
    else:
        pending_items.append((movement_id, record_findings))

pending_tab, reviewed_tab = st.tabs(
    [f"Pendentes ({len(pending_items) + len(unidentified_items)})", f"Revisadas ({len(reviewed_items)})"]
)
with pending_tab:
    if not pending_items and not unidentified_items:
        st.info("Não há ocorrências pendentes de revisão.")
    for movement_id, record_findings in [*pending_items, *unidentified_items]:
        show_occurrence(movement_id, record_findings)
with reviewed_tab:
    if not reviewed_items:
        st.info("Nenhuma ocorrência foi marcada como revisada ainda.")
    for movement_id, record_findings in reviewed_items:
        show_occurrence(movement_id, record_findings)

st.subheader("Como os dados se complementam")
st.markdown("PNCP: contratação e itens · Compras.gov.br: CATMAT e preços praticados · Portal da Transparência: convênios, recursos e execução. A integração em tempo real requer filtros e, para Transparência, chave de API.")
