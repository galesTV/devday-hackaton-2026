from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from sentinela_alimentos.collection import collect_food_data
from sentinela_alimentos.demo_data import sample_movements
from sentinela_alimentos.reports import build_report, export_pdf
from sentinela_alimentos.rules import run_all_rules
from sentinela_alimentos.session_state import public_movements, save_public_result

st.set_page_config(page_title="Sentinela Alimentos", page_icon="🌿", layout="wide")
css_path = Path(__file__).parent / "frontend" / "styles.css"
st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

if "review_status" not in st.session_state:
    st.session_state.review_status = {}
if "live_result" not in st.session_state:
    st.session_state.live_result = None
if "live_search_completed" not in st.session_state:
    st.session_state.live_search_completed = False

with st.sidebar:
    st.markdown('<div class="brand-mark">🌿</div><div class="brand-name">Sentinela<br>Alimentos</div>', unsafe_allow_html=True)
    st.caption("TRANSPARÊNCIA · ALIMENTAÇÃO PÚBLICA")
    page = st.radio("Navegação", ["Início", "Compras públicas", "Ocorrências", "Relatórios", "Sobre e fontes"], label_visibility="collapsed", key="page_navigation")
    st.markdown("<div class='side-divider'></div>", unsafe_allow_html=True)
    mode = st.radio("Origem dos dados", ["Demonstração simulada", "Fonte oficial"], help="A demonstração usa registros fictícios. A consulta oficial acessa APIs públicas.")
    is_demo = mode == "Demonstração simulada"
    st.markdown(f"<div class='mode-pill'>{'● DEMONSTRAÇÃO' if is_demo else '● FONTE OFICIAL'}</div>", unsafe_allow_html=True)

result = st.session_state.live_result
movements = sample_movements() if is_demo else public_movements(st.session_state)
if not is_demo:
    with st.sidebar:
        st.markdown("#### Consultar compras")
        product = st.text_input("Alimento", value="arroz")
        states = ["Todas", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
        state = st.selectbox("Região · UF", states)
        start = st.date_input("De", value=date.today() - timedelta(days=30))
        end = st.date_input("Até", value=date.today())
        if st.button("Buscar dados públicos", type="primary", use_container_width=True):
            save_public_result(st.session_state, collect_food_data(product, start, end, None if state == "Todas" else state))
            st.rerun()
    result = st.session_state.live_result
    movements = result.movements if result else []

findings = run_all_rules(movements)
grouped = defaultdict(list)
for finding in findings:
    grouped[finding.movement_id].append(finding)
by_id = {item.id: item for item in movements if item.id}
alert_total = sum(f.alert_type == "alert" for f in findings)
source_count = len({str(item.source) for item in movements})


def status_key(item_id: str, source: str) -> str:
    return f"{source}:{item_id}"


def occurrence_status(item_id: str, source: str) -> str:
    key = status_key(item_id, source)
    status = st.session_state.get(f"status-{key}")
    if status not in {"Para revisar", "Revisado", "Revisada", "Sem dados suficientes"}:
        status = st.session_state.review_status.get(key, "Para revisar")
    st.session_state.review_status[key] = status
    return status


reviewed = sum(
    occurrence_status(item.id, str(item.source)) in {"Revisado", "Revisada"}
    for item in movements
    if item.id
)


def header(eyebrow, title, desc=""):
    st.markdown(f"<div class='eyebrow'>{eyebrow}</div><h1 class='page-title'>{title}</h1>{f'<p class=\"page-deck\">{desc}</p>' if desc else ''}", unsafe_allow_html=True)

def go_to_purchases():
    st.session_state.page_navigation = "Compras públicas"

def mode_note():
    if is_demo:
        st.info("Dados simulados para demonstração. Estes registros são fictícios e não representam compras oficiais.")
    elif result:
        for error in result.errors:
            st.warning(error)
        if result.duplicates_removed:
            st.caption(f"{result.duplicates_removed} registro(s) repetido(s) removido(s) durante a coleta.")
        if result.truncated:
            st.caption("A visualização foi limitada aos primeiros 100 registros únicos.")
        st.caption("Fonte oficial · registros retornados pelas APIs consultadas. Preços CATMAT são usados como referência regional.")
    elif not st.session_state.live_search_completed:
        st.info("Defina os filtros na barra lateral e busque para consultar as fontes públicas.")
    else:
        st.info("A consulta terminou sem registros utilizáveis. Ajuste os filtros ou confira as mensagens das fontes.")

def metrics():
    cols = st.columns(4)
    for col, label, value, foot in zip(cols,
        ["Registros", "Alertas identificados", "Ocorrências revisadas", "Fontes consultadas"],
        [len(movements), alert_total, reviewed, source_count],
        ["no conjunto atual", "pedem revisão humana", "na sua fila", "com registros presentes"]):
        with col:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-foot'>{foot}</div></div>", unsafe_allow_html=True)

def occurrence_card(movement_id):
    item = by_id.get(movement_id)
    record_findings = grouped[movement_id]
    if not item:
        st.warning("Registro sem identificador rastreável")
        for finding in record_findings:
            st.write(f"**{finding.rule}** · {finding.explanation}")
        return
    with st.container(border=True):
        title = item.description or "Descrição ausente"
        st.markdown(f"<span class='tag tag-tomato'>{' · '.join(dict.fromkeys(f.rule for f in record_findings))}</span>", unsafe_allow_html=True)
        st.markdown(f"### {title}")
        st.caption(f"{item.id}  ·  {item.source}  ·  {item.municipality or 'Local não informado'}{f', {item.state}' if item.state else ''}")
        for finding in record_findings:
            if finding.alert_type == "insufficient_evidence":
                st.info(f"**Sem dados suficientes · {finding.rule}** — {finding.explanation}")
            else:
                st.warning(f"**Para revisar · {finding.rule}** — {finding.explanation}")
        cols = st.columns(4)
        cols[0].metric("Preço unitário", f"R$ {item.unit_price:.2f}" if item.unit_price is not None else "Indisponível")
        cols[1].metric("Quantidade", f"{item.quantity} {item.unit or ''}" if item.quantity is not None else "Indisponível")
        cols[2].metric("Valor total", f"R$ {item.total_value:.2f}" if item.total_value is not None else "Indisponível")
        review_key = status_key(item.id, str(item.source))
        current = occurrence_status(item.id, str(item.source))
        new_status = cols[3].selectbox("Status", ["Para revisar", "Revisado", "Sem dados suficientes"], index=["Para revisar", "Revisado", "Sem dados suficientes"].index(current) if current in ["Para revisar", "Revisado", "Sem dados suficientes"] else 0, key=f"status-{review_key}")
        st.session_state.review_status[review_key] = new_status
        actions = st.columns([1, 1, 3])
        if item.source_url:
            actions[0].link_button("Abrir fonte ↗", item.source_url, use_container_width=True)
        report = build_report(item, record_findings, simulated=is_demo)
        actions[1].download_button("PDF do registro", export_pdf(report), file_name=f"sentinela-{item.source}-{item.id}.pdf".replace("/", "-"), mime="application/pdf", key=f"report-{review_key}", use_container_width=True)

if page == "Início":
    st.markdown("<div class='hero'><div class='hero-copy'><div class='eyebrow'>CONTROLE SOCIAL · COMPRAS PÚBLICAS</div><h1>O que você come também é uma questão pública.</h1><p>Acompanhe compras de alimentos, entenda os sinais e ajude a fortalecer a transparência na alimentação pública.</p><span class='hero-note'>🌱 Dados públicos, explicações claras e revisão humana.</span></div><div class='hero-art'>✳<span>◌</span>❋</div></div>", unsafe_allow_html=True)
    mode_note()
    metrics()
    a, b = st.columns([1.2, .8])
    with a:
        st.markdown("### Um olhar atento, sem conclusões precipitadas")
        st.write("O Sentinela reúne registros públicos e destaca situações que podem merecer uma segunda análise. Cada sinal vem acompanhado de contexto para facilitar a conferência.")
        st.markdown("<div class='notice'><b>Um alerta não comprova fraude.</b><br>Ele aponta uma anomalia que requer revisão humana. Diferenças de produto, embalagem, frete, local ou período podem explicar os valores.</div>", unsafe_allow_html=True)
    with b:
        st.markdown("<div class='feature-card'><span class='feature-icon'>✿</span><div class='eyebrow'>SEU PRÓXIMO PASSO</div><h3>Explore as compras</h3><p>Busque por alimento, órgão ou fornecedor e consulte os detalhes de cada registro.</p></div>", unsafe_allow_html=True)
        st.button("Explorar compras →", type="primary", key="go-purchases", on_click=go_to_purchases)
    st.markdown("### Sinais recentes")
    ids = list(grouped)[:3]
    if ids:
        for movement_id in ids:
            occurrence_card(movement_id)
    else:
        st.markdown("<div class='empty-state'>✿<br><b>Nenhum sinal nesta consulta</b><br>Os registros aparecerão aqui quando houver dados para analisar.</div>", unsafe_allow_html=True)
elif page == "Compras públicas":
    header("PAINEL DE DADOS", "Compras públicas", "Explore registros de aquisição e referências públicas de preço.")
    mode_note()
    qcol, regioncol, statuscol = st.columns([2, 1, 1])
    query = qcol.text_input("Buscar alimento, fornecedor ou órgão", placeholder="Ex.: arroz, cooperativa, prefeitura")
    regions = ["Todas"] + sorted({item.state for item in movements if item.state})
    region = regioncol.selectbox("Região", regions)
    situation = statuscol.selectbox("Situação", ["Todas", "Com alerta", "Sem alerta"])
    visible = [item for item in movements if (not query or query.casefold() in " ".join(filter(None, [item.description, item.supplier_name, item.buyer_name])).casefold()) and (region == "Todas" or item.state == region) and (situation == "Todas" or bool(grouped.get(item.id)) == (situation == "Com alerta"))]
    st.caption(f"{len(visible)} registros · {source_count} fontes")
    for item in visible:
        findings_here = grouped.get(item.id, [])
        with st.expander(f"{item.description or 'Descrição ausente'}  ·  {item.source}  ·  {item.id}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Preço unitário", f"R$ {item.unit_price:.2f}" if item.unit_price is not None else "Indisponível")
            c2.write(f"**Unidade:** {item.unit or 'Não informada'}")
            c3.write(f"**Órgão:** {item.buyer_name or 'Não informado'}")
            st.write(f"**Fornecedor:** {item.supplier_name or 'Não informado'} · **Quantidade:** {item.quantity if item.quantity is not None else 'Não informada'}")
            if findings_here:
                st.warning(f"{len(findings_here)} sinal(is) associado(s) · confira em Ocorrências.")
            if item.source_url:
                st.link_button("Consultar registro na fonte oficial ↗", item.source_url)
    if not visible:
        st.markdown("<div class='empty-state'>✿<br><b>Nenhuma compra encontrada</b><br>Experimente mudar a busca ou a região.</div>", unsafe_allow_html=True)
elif page == "Ocorrências":
    header("REVISÃO HUMANA", "Ocorrências", "Sinais explicáveis para apoiar a conferência dos registros.")
    mode_note()
    pending_ids = []
    reviewed_ids = []
    for movement_id in grouped:
        item = by_id.get(movement_id)
        status = occurrence_status(movement_id, str(item.source)) if item else "Para revisar"
        if status in {"Revisado", "Revisada"}:
            reviewed_ids.append(movement_id)
        else:
            pending_ids.append(movement_id)

    pending_tab, reviewed_tab = st.tabs(
        [f"Para revisar · {len(pending_ids)}", f"Revisadas · {len(reviewed_ids)}"]
    )
    for tab, movement_ids in [(pending_tab, pending_ids), (reviewed_tab, reviewed_ids)]:
        with tab:
            categories = {"Duplicidade": [], "Preço atípico": [], "Dados ausentes": []}
            for movement_id in movement_ids:
                labels = " ".join(f.rule_id for f in grouped[movement_id])
                bucket = "Duplicidade" if "duplicate" in labels else "Preço atípico" if "price" in labels else "Dados ausentes"
                categories[bucket].append(movement_id)
            category_tabs = st.tabs(
                [f"{name} · {len(ids)}" for name, ids in categories.items()]
            )
            for category_tab, ids in zip(category_tabs, categories.values()):
                with category_tab:
                    if ids:
                        for movement_id in ids:
                            occurrence_card(movement_id)
                    else:
                        st.markdown("<div class='empty-state'>✿<br><b>Nada para revisar nesta categoria</b></div>", unsafe_allow_html=True)
elif page == "Relatórios":
    header("PRESTAÇÃO DE CONTAS", "Relatórios", "Resumos exportáveis dos registros e sinais exibidos no painel.")
    mode_note()
    metrics()
    st.markdown("### Exportar relatórios por registro")
    if grouped:
        for movement_id in grouped:
            item = by_id.get(movement_id)
            if item:
                report = build_report(item, grouped[movement_id], simulated=is_demo)
                with st.container(border=True):
                    left, right = st.columns([3, 1])
                    left.write(f"**{item.description or 'Descrição ausente'}** · {item.source} · {item.id}")
                    right.download_button("Baixar PDF", export_pdf(report), file_name=f"sentinela-{item.id}.pdf".replace("/", "-"), mime="application/pdf", key=f"report-page-{movement_id}", use_container_width=True)
    else:
        st.success("Nenhuma ocorrência disponível para incluir em um relatório.")
    st.caption("Os PDFs usam diretamente a prévia e o exportador de src/sentinela_alimentos/reports.py.")
else:
    header("SOBRE O PROJETO", "Transparência que alimenta a confiança", "Uma ferramenta cívica para acompanhar compras públicas de alimentos.")
    st.markdown("<div class='notice'><b>Como interpretar:</b> alertas são sinais de triagem e pedem revisão humana. Não constituem comprovação de fraude ou superfaturamento. A ausência de alerta também não comprova regularidade.</div>", unsafe_allow_html=True)
    st.markdown("### Fontes oficiais")
    st.markdown("- [PNCP · Portal Nacional de Contratações Públicas](https://pncp.gov.br/api/consulta/swagger-ui/index.html) — contratações e itens.\n- [Compras.gov.br · Dados Abertos](https://dadosabertos.compras.gov.br/swagger-ui/index.html) — catálogo CATMAT e preços praticados.\n- [Portal da Transparência](https://api.portaldatransparencia.gov.br/swagger-ui/index.html) — convênios e transferências; requer chave de API.")
    st.markdown("### Como as fontes se complementam")
    st.write("PNCP informa contratações e itens; Compras.gov.br oferece catálogo e referências de preço; Portal da Transparência acrescenta contexto sobre transferências e execução. Os registros são apresentados com sua origem para facilitar a verificação.")
