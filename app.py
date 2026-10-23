from collections import defaultdict
from datetime import date, timedelta

import httpx
import streamlit as st

from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.live_data import (
    compras_food_catalog,
    compras_regional_market_prices,
    pncp_food_movements,
    transparency_food_agreements,
)
from sentinela_alimentos.rules import (
    find_regional_price_discrepancies,
    run_all_rules,
)

st.set_page_config(page_title="Sentinela Alimentos", page_icon="🌾", layout="wide")
st.title("🌾 Sentinela Alimentos")
st.caption("Conferência explicável de compras públicas de alimentos — um sinal pede revisão; não é conclusão de fraude.")

if "review_status" not in st.session_state:
    st.session_state.review_status = {}

mode = st.sidebar.radio("Dados", ["Demonstração reproduzível", "Consultar APIs oficiais"])
movements = sample_movements()
if mode == "Consultar APIs oficiais":
    st.sidebar.caption("PNCP e Compras.gov.br são públicos. O Portal da Transparência requer `TRANSPARENCIA_API_KEY`.")
    product = st.sidebar.text_input("Produto alimentar", value="arroz")
    start = st.sidebar.date_input("Data inicial", value=date.today() - timedelta(days=30))
    end = st.sidebar.date_input("Data final", value=date.today())
    if st.sidebar.button("Buscar dados públicos", type="primary"):
        with st.spinner("Consultando fontes oficiais..."):
            errors: list[str] = []
            movements = []
            for source_name, collector, arguments in [
                ("PNCP", pncp_food_movements, (start, end, product)),
                ("Compras.gov.br", compras_food_catalog, (product,)),
                ("Portal da Transparência", transparency_food_agreements, (start, end)),
            ]:
                try:
                    movements.extend(collector(*arguments))
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    errors.append(f"{source_name}: {exc}")
            for error in errors:
                st.warning(error)
            pncp_purchases = [item for item in movements if item.source == "PNCP"]
            market_prices = []
            for state_code, municipality_code in {
                (item.state, item.municipality_code) for item in pncp_purchases
            }:
                try:
                    market_prices.extend(
                        compras_regional_market_prices(
                            product, state_code, municipality_code
                        )
                    )
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    st.warning(f"Referência regional Compras.gov.br: {exc}")
            movements.extend(market_prices)
            if not movements:
                st.info("Nenhum registro alimentar encontrado para estes filtros. Tente um período ou produto diferente.")
    else:
        st.info("Defina os filtros e clique em “Buscar dados públicos”.")
by_id = {item.id: item for item in movements}
findings = run_all_rules(movements)
findings += find_regional_price_discrepancies(
    [item for item in movements if item.source == "PNCP"],
    [item for item in movements if item.source == "Compras.gov.br" and item.unit_price],
)
grouped = defaultdict(list)
for finding in findings:
    grouped[finding.movement_id].append(finding)

total = len(grouped)
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
            st.warning(f"**{finding.rule}** — {finding.explanation}")
        c1, c2, c3 = st.columns(3)
        c1.write(f"Valor: R$ {item.total_value or 0:.2f}")
        c2.write(f"Fornecedor: {item.supplier_name or 'não informado'}")
        status = c3.radio("Status", ["Pendente", "Revisada"], key=f"status-{movement_id}", horizontal=True)
        st.session_state.review_status[movement_id] = status

st.subheader("Como os dados se complementam")
st.markdown("PNCP: contratação e itens · Compras.gov.br: CATMAT e preços praticados · Portal da Transparência: convênios, recursos e execução. A integração em tempo real requer filtros e, para Transparência, chave de API.")
