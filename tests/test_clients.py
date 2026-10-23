import httpx

from sentinela_alimentos.clients import PNCPClient


def test_pncp_publications_sends_the_selected_state_filter():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/consulta/v1/contratacoes/publicacao"
        assert request.url.params["uf"] == "SP"
        assert request.url.params["dataInicial"] == "20261001"
        return httpx.Response(200, json={"data": []})

    client = PNCPClient()
    client.client.close()
    client.client = httpx.Client(
        base_url="https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.publications("2026-10-01", "2026-10-23", state="SP") == []
    finally:
        client.close()
