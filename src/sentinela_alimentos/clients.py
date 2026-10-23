"""Conectores mínimos: cada resposta é preservada e depois normalizada."""

from collections.abc import Mapping
from typing import Any

import httpx


class PublicApiClient:
    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        headers = {"chave-api-dados": api_key} if api_key else {}
        self.client = httpx.Client(base_url=base_url, timeout=30, headers=headers)

    def get_list(self, endpoint: str, params: Mapping[str, str | int] | None = None) -> list[dict[str, Any]]:
        response = self.client.get(endpoint, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "content", "resultado"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise ValueError("Formato de resposta inesperado; consulte a documentação da fonte.")

    def close(self) -> None:
        self.client.close()


class PNCPClient(PublicApiClient):
    def __init__(self) -> None:
        super().__init__("https://pncp.gov.br/api/consulta")

    def publications(self, start: str, end: str, modality: int = 6) -> list[dict[str, Any]]:
        return self.get_list("/v1/contratacoes/publicacao", {"dataInicial": start.replace("-", ""), "dataFinal": end.replace("-", ""), "codigoModalidadeContratacao": modality, "pagina": 1, "tamanhoPagina": 50})


class ComprasGovClient(PublicApiClient):
    def __init__(self) -> None:
        super().__init__("https://dadosabertos.compras.gov.br")

    def practiced_material_prices(self, params: Mapping[str, str | int]) -> list[dict[str, Any]]:
        return self.get_list("/modulo-pesquisa-preco/1_consultarMaterial", params)


class TransparencyClient(PublicApiClient):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Defina TRANSPARENCIA_API_KEY para consultar esta fonte.")
        super().__init__("https://api.portaldatransparencia.gov.br", api_key=api_key)

    def agreements(self, params: Mapping[str, str | int]) -> list[dict[str, Any]]:
        return self.get_list("/api-de-dados/convenios", params)
