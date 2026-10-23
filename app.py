from collections import defaultdict
from datetime import date, timedelta

import streamlit as st

from sentinela_alimentos.collection import collect_food_data
from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.reports import build_report, export_pdf
from sentinela_alimentos.rules import find_regional_price_discrepancies, run_all_rules

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
movements = sample_movements() if is_demo else (result.movements if result else [])
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
        st.session_state.live_result = collect_food_data(
            product, start, end, None if state == "Todas" else state
        )
        st.session_state.review_status = {}
        st.session_state.live_search_completed = True
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
        st.caption("Registros reais retornados pelas fontes oficiais; preços CATMAT são usados apenas como referência na regra regional.")

findings = run_all_rules(movements)
findings += find_regional_price_discrepancies(
    [item for item in movements if item.source == "PNCP"],
    [item for item in movements if item.source == "Compras.gov.br" and item.unit_price],
)
grouped = defaultdict(list)
for finding in findings:
    grouped[finding.movement_id].append(finding)

statuses = [st.session_state.review_status.get(f"{f.movement_id}|{f.rule}", "Pendente") for f in findings]
cols = st.columns(4)
cols[0].metric("Registros analisados", len(movements))
cols[1].metric("Ocorrências", len(findings))
cols[2].metric("Pendentes", statuses.count("Pendente"))
cols[3].metric("Revisadas", statuses.count("Revisada"))

st.subheader("Registros analisados")
for item in movements:
    item_findings = grouped.get(item.id, [])
    origin_label = f"Simulado (fixture: {item.source})" if is_demo else str(item.source)
    label = f"{item.id} · {origin_label} · {item.description or 'Descrição ausente'}"
    with st.expander(label, expanded=bool(item_findings)):
        st.write(f"**Descrição:** {item.description or 'não informada'}")
        st.write(f"**Preço unitário:** {('R$ ' + format(item.unit_price, '.2f')) if item.unit_price is not None else 'indisponível'} · **Quantidade/unidade:** {item.quantity or '—'} {item.unit or ''}")
        st.write(f"**Data:** {item.event_date or 'não informada'} · **Origem:** {origin_label}")
        st.write(f"**Órgão:** {item.buyer_name or 'não informado'} · **Fornecedor:** {item.supplier_name or 'não informado'} · **Município:** {item.municipality or 'não informado'}")
        if item.source_url:
            st.markdown(f"[Consultar fonte oficial]({item.source_url})")
        for finding in item_findings:
            display = (
                st.info
                if finding.alert_type == "insufficient_evidence"
                else st.warning
            )
            display(f"**{finding.rule}** — {finding.explanation}")
            key = f"{item.id}|{finding.rule}"
            st.radio("Revisão desta ocorrência (estado apenas nesta sessão)", ["Pendente", "Revisada"], key=f"review-{key}", index=1 if st.session_state.review_status.get(key) == "Revisada" else 0, horizontal=True, on_change=lambda k=key: st.session_state.review_status.__setitem__(k, st.session_state[f"review-{k}"]))

st.subheader("Relatório cidadão")
if not movements:
    st.caption("Carregue ou selecione registros para preparar um relatório.")
else:
    choices = [f"{item.id} — {item.description or 'Descrição ausente'}" for item in movements]
    selected = st.selectbox("Movimentação", choices)
    item = movements[choices.index(selected)]
    selected_findings = grouped.get(item.id, [])
    observations = st.text_area("Observações complementares do cidadão")
    report = build_report(item, selected_findings, observations=observations, simulated=is_demo)
    st.markdown(report["text"])
    st.download_button("Gerar relatório", data=export_pdf(report), file_name=f"relatorio-{item.id.replace(':', '-')}.pdf", mime="application/pdf")

st.caption("Demonstração simulada usa exclusivamente registros fictícios. Estado de revisão não é salvo permanentemente.")
