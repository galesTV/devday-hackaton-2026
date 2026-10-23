import httpx

from sentinela_alimentos import clients
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


def test_client_retries_rate_limit_before_returning_data(monkeypatch):
    responses = iter([httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200, json={"data": []})])
    client = PNCPClient()
    client.client.close()
    client.client = httpx.Client(
        base_url="https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(lambda _request: next(responses)),
    )
    monkeypatch.setattr(clients.time, "sleep", lambda _delay: None)
    try:
        assert client.publications("2026-10-01", "2026-10-23", state="SP") == []
    finally:
        client.close()
