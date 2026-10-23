from collections import defaultdict

import streamlit as st

from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.rules import run_all_rules

st.set_page_config(page_title="Sentinela Alimentos", page_icon="🌾", layout="wide")
st.title("🌾 Sentinela Alimentos")
st.caption("Conferência explicável de compras públicas de alimentos — um sinal pede revisão; não é conclusão de fraude.")

if "review_status" not in st.session_state:
    st.session_state.review_status = {}

movements = sample_movements()
by_id = {item.id: item for item in movements}
findings = run_all_rules(movements)
grouped = defaultdict(list)
for finding in findings:
    grouped[finding.movement_id].append(finding)

total = sum(finding.alert_type == "alert" for finding in findings)
reviewed = sum(status == "Revisada" for status in st.session_state.review_status.values())
one, two, three = st.columns(3)
one.metric("Registros demonstrados", len(movements))
two.metric("Ocorrências sinalizadas", total)
three.metric("Revisadas", reviewed)

st.subheader("Ocorrências para revisão")
for movement_id, record_findings in grouped.items():
    item = by_id[movement_id]
    with st.expander(f"{movement_id} · {item.source} · {item.description or 'Descrição ausente'}", expanded=True):
        for finding in record_findings:
            display = st.info if finding.alert_type == "insufficient_evidence" else st.warning
            display(f"**{finding.rule}** — {finding.explanation}")
        c1, c2, c3 = st.columns(3)
        c1.write(f"Valor: R$ {item.total_value or 0:.2f}")
        c2.write(f"Fornecedor: {item.supplier_name or 'não informado'}")
        status = c3.radio("Status", ["Pendente", "Revisada"], key=f"status-{movement_id}", horizontal=True)
        st.session_state.review_status[movement_id] = status

st.subheader("Como os dados se complementam")
st.markdown("PNCP: contratação e itens · Compras.gov.br: CATMAT e preços praticados · Portal da Transparência: convênios, recursos e execução. A integração em tempo real requer filtros e, para Transparência, chave de API.")
