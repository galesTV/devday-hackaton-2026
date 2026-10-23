# 🌾 Sentinela Alimentos

MVP para o Dev Day: uma fila de revisão de movimentações de compras públicas de alimentos. Ele une, em um modelo de leitura comum, três fontes oficiais:

- **PNCP**: publicações, contratações e itens;
- **Compras.gov.br**: CATMAT e referências de preços praticados;
- **Portal da Transparência**: convênios, transferências e execução federal.

O sistema sinaliza evidências para conferência humana, nunca uma conclusão automática de fraude.

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
