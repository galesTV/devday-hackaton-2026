# 🌾 Sentinela Alimentos

MVP para o Dev Day: uma fila de revisão de movimentações de compras públicas de alimentos. Ele une, em um modelo de leitura comum, três fontes oficiais:

- **PNCP**: publicações, contratações e itens;
- **Compras.gov.br**: CATMAT e referências de preços praticados;
- **Portal da Transparência**: convênios, transferências e execução federal.

O sistema sinaliza evidências para conferência humana, nunca uma conclusão automática de fraude.

## Consultas reais às fontes

Na barra lateral, selecione **Consultar APIs oficiais**. O sistema busca:

- **PNCP**: publicações de pregão e, para objetos com termos alimentares, os respectivos itens. A API não possui busca textual para publicações, por isso o filtro ocorre localmente e é limitado a uma página de resultados.
- **Compras.gov.br**: itens CATMAT do grupo **89 — Subsistência**, que inclui carnes, hortifrúti, cereais e laticínios. A busca por produto é feita nas descrições do catálogo; o endpoint de preços praticados requer `tipo=codigoItemCatalogo` ou `codigoPdm`.
- **Portal da Transparência**: convênios no período, filtrados localmente pelo objeto. Defina `TRANSPARENCIA_API_KEY` antes de usar esta fonte, pois a API rejeita consultas sem chave.

O filtro de **UF** é aplicado ao PNCP e ao Portal da Transparência; no Compras.gov.br, a mesma UF — e o município quando disponível — orienta a referência regional de preço. A última consulta pública fica mantida na sessão para que marcar uma ocorrência como revisada não volte aos dados fictícios.

## Demonstração pronta

O modo demonstrativo usa seis registros fictícios (abaixo do limite de 100) e cobre os três critérios do desafio:

1. duplicidade: dois registros de tomate com item, fornecedor, data e valor iguais;
2. valor fora do critério: tomate a R$ 18/kg, acima de 1,5× a mediana dos comparáveis;
3. informação obrigatória: transferência sem descrição e fornecedor.

Cada ocorrência possui explicação, origem e seletor **Pendente/Revisada**.

## Critérios e formato dos alertas

`run_all_rules(movements)` preserva a assinatura e retorna uma lista de `Finding`, associada ao registro original por `movement_id`. Além dos campos existentes (`rule`, `explanation`, `severity`), cada resultado inclui `rule_id`, `alert_type`, `criteria`, `evidence` e `limitations`. `alert_type` vale `alert` para sinal acionado ou `insufficient_evidence` quando uma comparação de preço não tem amostra adequada. A interface exibe o segundo como informação, e não como alerta.

- **Duplicidade:** ID repetido no mesmo lote é tratado como duplicidade confirmada por identificador. Similaridade exige descrição, fornecedor, data, valor total, quantidade e unidade iguais; comprador, município e UF, quando presentes nos dois registros, também não podem divergir. Valor igual isoladamente nunca gera alerta. O resultado inclui os IDs e os campos coincidentes.
- **Preço:** limite configurável por `multiplier`, padrão existente de `1.5` vezes a mediana. A comparação exige descrição, categoria, unidade e ano iguais e três ou mais referências válidas externas ao registro. Informa mediana, quantidade e IDs das referências, limiar e divergência percentual `(preço - mediana) / mediana × 100`. Não há conversão de unidades. Sem amostra mínima, retorna `insufficient_evidence`.
- **Dados obrigatórios:** ID para rastreabilidade; descrição, fornecedor, data e valor total para duplicidade; descrição, categoria, unidade, data e preço unitário para comparar preços. Quantidade também integra a chave de similaridade. Campos opcionais como URL e localização ausentes não geram alerta por si só. Ausência/invalidade limita a análise e não implica fraude.

Exemplo de campos adicionais do retorno:

```python
{
    "movement_id": "pncp-003",
    "rule_id": "price_outlier",
    "rule": "Valor fora do critério",
    "alert_type": "alert",
    "criteria": {"multiplier": "1.5", "minimum_references": 3},
    "evidence": {
        "price": "18.00", "reference_median": "7.8",
        "threshold": "11.70", "divergence_percent": "130.7",
        "reference_count": 4, "reference_ids": ["..."]
    },
    "limitations": ["Comparação textual exata; não há conversão de unidade."]
}
```

## Executar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
streamlit run app.py
```

Testes:

```powershell
pytest
```

## Integração de dados reais

Os conectores em `src/sentinela_alimentos/clients.py` apontam às APIs oficiais. O Portal da Transparência requer chave própria; copie `.env.example` para `.env` e defina `TRANSPARENCIA_API_KEY`. Durante a apresentação, priorize o dataset fictício: ele torna a demonstração reproduzível e respeita o limite do desafio.

O cruzamento responsável usa: descrição/CATMAT e unidade para preço, CNPJ/nome para fornecedor, município/UF e período para contexto, e convênio/transferência como trilha de financiamento. Não se deve comparar preços de unidades ou especificações diferentes.

## Gitflow

O trabalho desta entrega está na branch `feature/integracao-fontes-alimentos`, criada a partir de `develop`. Proposta de fluxo: `feature/*` → PR para `develop` → `release/*` para a demonstração → merge em `main` e tag da versão.

## Análise explicativa com IA (opcional)

A página **Análise com IA** usa a API oficial da OpenAI pelo SDK Python e pela Responses API. O modelo padrão é `gpt-6-luna`; pode ser alterado com `OPENAI_MODEL`. A IA só é chamada após uma análise ou pergunta explícita, recebe no máximo cinco registros selecionados e explica regras e evidências já calculadas pelo sistema. Ela não consulta a internet, cria referências de preço ou comprova irregularidades. A análise pode ser incluída nos PDFs como interpretação assistida por IA, separada dos fatos fornecidos.

No Windows, copie `.env.example` para `.env` e preencha `OPENAI_API_KEY` com uma chave criada em <https://platform.openai.com/api-keys>. O `.env` já está no `.gitignore`; não coloque chaves no código, no repositório ou em prints/logs. Também é possível definir a variável só para a sessão do PowerShell:

```powershell
$env:OPENAI_API_KEY = "sua-chave-nova"
streamlit run app.py
```

Instale as dependências com `pip install -e ".[dev]"`. Sem chave, o painel informa que a integração está pendente e não apresenta respostas simuladas. O uso da API pode gerar cobrança conforme a conta, o modelo e os tokens enviados.

## Fontes

- [PNCP — API de consulta](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
- [Compras.gov.br — dados abertos](https://dadosabertos.compras.gov.br/swagger-ui/index.html)
- [Portal da Transparência — API](https://api.portaldatransparencia.gov.br/swagger-ui/index.html)
