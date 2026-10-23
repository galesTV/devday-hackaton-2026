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

Selecione uma **UF** para restringir PNCP e Portal da Transparência ao estado escolhido e usar essa localização como referência de preços no Compras.gov.br. O resultado da última busca pública é mantido durante a sessão: marcar uma ocorrência como revisada não executa a coleta novamente nem retorna ao dataset demonstrativo.

### Origem, rastreabilidade e qualidade

| Fonte | Endpoints utilizados | Finalidade | Campos preservados |
| --- | --- | --- | --- |
| PNCP | `/v1/contratacoes/publicacao` e `/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens` | Contratações e itens alimentares | `numeroControlePNCP`, CNPJ, órgão, datas, município/UF, valores, fornecedor e link PNCP |
| Compras.gov.br | `/modulo-material/4_consultarItemMaterial` e `/modulo-pesquisa-preco/1_consultarMaterial` | CATMAT grupo 89 e preços praticados regionais | Código CATMAT, data, órgão/UASG, fornecedor, município/UF, quantidade e preço unitário |
| Portal da Transparência | `/api-de-dados/convenios` | Contexto de transferências e convênios ligados à alimentação | ID/número, convenente, órgão, vigência, município/UF e valor liberado/global |

A coleta converte todas as respostas em `FoodMovement`, mantém o payload bruto em `raw`, isola falhas por fonte e remove repetições somente dentro da mesma origem/identificador. Registros de fontes diferentes nunca são mesclados. A detecção de duplicidade exibe um único grupo revisável, em vez de repetir um alerta para cada linha idêntica. A visualização limita a fila aos primeiros 100 registros únicos, mantendo o escopo da demonstração controlado.

Em 23/10/2026, os testes manuais retornaram registros de gêneros alimentícios no PNCP, itens CATMAT de arroz no Compras.gov.br e referências regionais de arroz para DF/Brasília. O Portal da Transparência respondeu à consulta autenticada; para convênios, a API limita consultas por período a um mês.

## Demonstração pronta

O modo demonstrativo usa seis registros fictícios (abaixo do limite de 100) e cobre os três critérios do desafio:

1. duplicidade: dois registros de tomate com item, fornecedor, data e valor iguais;
2. valor fora do critério: tomate a R$ 18/kg, acima de 1,5× a mediana dos comparáveis;
3. informação obrigatória: transferência sem descrição e fornecedor.

Cada ocorrência possui explicação, origem e seletor **Pendente/Revisada**.

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

## Fontes

- [PNCP — API de consulta](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
- [Compras.gov.br — dados abertos](https://dadosabertos.compras.gov.br/swagger-ui/index.html)
- [Portal da Transparência — API](https://api.portaldatransparencia.gov.br/swagger-ui/index.html)
