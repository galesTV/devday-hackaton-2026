import json
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import streamlit as st

from sentinela_alimentos.ai_service import (
    AIServiceError,
    analyze_records,
    build_factual_context,
)
from sentinela_alimentos.ai_service import is_configured as ai_is_configured
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
if "ai_cache" not in st.session_state:
    st.session_state.ai_cache = {}
if "ai_chat_history" not in st.session_state:
    st.session_state.ai_chat_history = {}
if "ai_report_summaries" not in st.session_state:
    st.session_state.ai_report_summaries = {}

with st.sidebar:
    st.markdown('<div class="brand-mark">🌿</div><div class="brand-name">Sentinela<br>Alimentos</div>', unsafe_allow_html=True)
    st.caption("TRANSPARÊNCIA · ALIMENTAÇÃO PÚBLICA")
    page = st.radio("Navegação", ["Início", "Compras públicas", "Ocorrências", "Relatórios", "Análise com IA", "Sobre e fontes"], label_visibility="collapsed", key="page_navigation")
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


def ai_summary_text(record):
    sections = [
        f"Resumo: {record['summary']}",
        f"Explicação do alerta: {record['alert_explanation']}",
        f"Interpretação das evidências fornecidas: {record['evidence_interpretation']}",
    ]
    for heading, key in [
        ("Possíveis explicações alternativas", "alternative_explanations"),
        ("O que verificar", "verification_needed"),
        ("Próximos passos", "citizen_next_steps"),
        ("Limitações", "limitations"),
    ]:
        sections.append(f"{heading}: " + ("; ".join(record[key]) or "Não informado pelo modelo."))
    return "\n".join(sections)


def remember_ai_summaries(result):
    for analyzed in result["interpretation"]["records"]:
        item = by_id.get(analyzed["record_id"])
        if item:
            st.session_state.ai_report_summaries[f"{item.source}:{item.id}"] = ai_summary_text(analyzed)


def render_ai_interpretation(result):
    interpretation = result["interpretation"]
    st.markdown("#### Visão geral assistida por IA")
    st.write(interpretation["overview"])
    for analyzed in interpretation["records"]:
        with st.expander(f"Interpretação de IA · {analyzed['record_id']}", expanded=True):
            st.markdown(f"**Resumo**\n\n{analyzed['summary']}")
            st.markdown(f"**Explicação do alerta**\n\n{analyzed['alert_explanation']}")
            st.markdown(f"**Interpretação das evidências**\n\n{analyzed['evidence_interpretation']}")
            for heading, key in [
                ("Possíveis explicações alternativas", "alternative_explanations"),
                ("Informações a verificar", "verification_needed"),
                ("Próximos passos para o cidadão", "citizen_next_steps"),
                ("Limitações", "limitations"),
            ]:
                st.markdown(f"**{heading}**")
                if analyzed[key]:
                    for value in analyzed[key]:
                        st.markdown(f"- {value}")
                else:
                    st.caption("O modelo não sugeriu itens para esta seção.")
    st.caption("Conteúdo gerado por IA; interpretação explicativa, não comprovação de fraude ou irregularidade.")

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
        report = build_report(item, record_findings, simulated=is_demo, ai_summary=st.session_state.ai_report_summaries.get(review_key, ""))
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
                report = build_report(item, grouped[movement_id], simulated=is_demo, ai_summary=st.session_state.ai_report_summaries.get(f"{item.source}:{item.id}", ""))
                with st.container(border=True):
                    left, right = st.columns([3, 1])
                    left.write(f"**{item.description or 'Descrição ausente'}** · {item.source} · {item.id}")
                    right.download_button("Baixar PDF", export_pdf(report), file_name=f"sentinela-{item.id}.pdf".replace("/", "-"), mime="application/pdf", key=f"report-page-{movement_id}", use_container_width=True)
    else:
        st.success("Nenhuma ocorrência disponível para incluir em um relatório.")
    st.caption("Os PDFs usam diretamente a prévia e o exportador de src/sentinela_alimentos/reports.py.")
elif page == "Análise com IA":
    header("EXPLICAÇÃO CONTEXTUAL", "Análise com IA", "Peça uma explicação baseada nos registros e alertas já calculados pelo painel.")
    mode_note()
    if is_demo:
        st.warning("Os dados selecionados são fictícios e serão enviados ao provedor apenas como demonstração simulada.")
    if not ai_is_configured():
        st.info("Configuração pendente: defina OPENAI_API_KEY no ambiente ou em .env local (ignorado pelo Git) para habilitar chamadas reais.")
    unique_records = {f"{item.source}::{item.id}": item for item in movements if item.id}
    selected_keys = st.multiselect(
        "Registros para análise (até 5)",
        options=list(unique_records),
        format_func=lambda key: f"{unique_records[key].id} · {unique_records[key].description or 'Descrição ausente'}",
        max_selections=5,
    )
    selected_movements = [unique_records[key] for key in selected_keys]
    if selected_movements:
        selected_ids = {item.id for item in selected_movements}
        selected_findings = [finding for finding in findings if finding.movement_id in selected_ids]
        selected_context = build_factual_context(selected_movements, selected_findings, simulated=is_demo)
        context_key = sha256(json.dumps(selected_context, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        left, right = st.columns([1, 2])
        analyze_clicked = left.button("Analisar com IA", type="primary", key="analyze-selected")
        if context_key in st.session_state.ai_cache:
            right.caption("Análise anterior desta seleção reutilizada nesta sessão.")
        elif not ai_is_configured():
            right.caption("A análise só será solicitada após configurar a chave.")

        if analyze_clicked:
            try:
                with st.spinner("Analisando os registros selecionados…"):
                    result_ai = analyze_records(selected_movements, selected_findings, simulated=is_demo)
                st.session_state.ai_cache[context_key] = result_ai
                if len(st.session_state.ai_cache) > 10:
                    st.session_state.ai_cache.pop(next(iter(st.session_state.ai_cache)))
                remember_ai_summaries(result_ai)
                st.success("Análise concluída. Os fatos fornecidos e a interpretação da IA aparecem em seções separadas.")
            except AIServiceError as error:
                st.error(str(error))

        cached_analysis = st.session_state.ai_cache.get(context_key)
        if cached_analysis:
            st.markdown("### Evidências fornecidas ao modelo")
            for fact in cached_analysis["facts"]:
                with st.expander(f"{fact['record_id']} · {fact['source']}"):
                    st.write(f"**Item:** {fact['description'] or 'Não informado'} · **Categoria:** {fact['category'] or 'Não informada'}")
                    st.write(f"**Preço/unidade:** {fact['unit_price'] or 'Indisponível'} / {fact['unit'] or 'não informada'} · **Quantidade:** {fact['quantity'] or 'não informada'}")
                    st.write(f"**Local e período:** {fact['municipality'] or 'não informado'} / {fact['state'] or 'não informada'} · {fact['event_date'] or 'não informado'}")
                    for evidence in fact["findings"]:
                        st.write(f"**Regra calculada · {evidence['rule']}**: {evidence['explanation']}")
                        st.caption(f"Critério: {evidence['criteria']} · Evidência: {evidence['evidence']}")
                    if fact["source_url"]:
                        st.link_button("Abrir fonte disponível", fact["source_url"])
            render_ai_interpretation(cached_analysis)

        st.markdown("### Pergunte sobre esta seleção")
        if context_key not in st.session_state.ai_chat_history and len(st.session_state.ai_chat_history) >= 10:
            st.session_state.ai_chat_history.pop(next(iter(st.session_state.ai_chat_history)))
        history = st.session_state.ai_chat_history.setdefault(context_key, [])
        for message in history:
            with st.chat_message(message["role"]):
                st.text(message["content"])
        question = st.chat_input("Ex.: O que preciso verificar antes de concluir?")
        if question:
            with st.chat_message("user"):
                st.text(question)
            try:
                with st.spinner("Consultando a análise contextual…"):
                    answer = analyze_records(
                        selected_movements,
                        selected_findings,
                        question=question,
                        history=history,
                        simulated=is_demo,
                    )
                answer_text = answer["interpretation"]["chat_answer"]
                history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer_text}])
                history[:] = history[-12:]
                remember_ai_summaries(answer)
                st.rerun()
            except AIServiceError as error:
                st.error(str(error))
    else:
        st.markdown("<div class='empty-state'>✿<br><b>Escolha até cinco registros</b><br>A IA só recebe os registros selecionados quando você pede uma análise ou faz uma pergunta.</div>", unsafe_allow_html=True)
else:
    header("SOBRE O PROJETO", "Transparência que alimenta a confiança", "Uma ferramenta cívica para acompanhar compras públicas de alimentos.")
    st.markdown("<div class='notice'><b>Como interpretar:</b> alertas são sinais de triagem e pedem revisão humana. Não constituem comprovação de fraude ou superfaturamento. A ausência de alerta também não comprova regularidade.</div>", unsafe_allow_html=True)
    st.markdown("### Fontes oficiais")
    st.markdown("- [PNCP · Portal Nacional de Contratações Públicas](https://pncp.gov.br/api/consulta/swagger-ui/index.html) — contratações e itens.\n- [Compras.gov.br · Dados Abertos](https://dadosabertos.compras.gov.br/swagger-ui/index.html) — catálogo CATMAT e preços praticados.\n- [Portal da Transparência](https://api.portaldatransparencia.gov.br/swagger-ui/index.html) — convênios e transferências; requer chave de API.")
    st.markdown("### Como as fontes se complementam")
    st.write("PNCP informa contratações e itens; Compras.gov.br oferece catálogo e referências de preço; Portal da Transparência acrescenta contexto sobre transferências e execução. Os registros são apresentados com sua origem para facilitar a verificação.")
