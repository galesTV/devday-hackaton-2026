"""Conectores mínimos: cada resposta é preservada e depois normalizada."""

import time
from collections.abc import Mapping
from typing import Any

import httpx


class PublicApiClient:
    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        headers = {"chave-api-dados": api_key} if api_key else {}
        self.client = httpx.Client(base_url=base_url, timeout=30, headers=headers)

    def get_list(self, endpoint: str, params: Mapping[str, str | int] | None = None) -> list[dict[str, Any]]:
        response: httpx.Response | None = None
        for attempt in range(3):
            response = self.client.get(endpoint, params=params)
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == 2:
                break
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
            except ValueError:
                delay = 0.5 * (2**attempt)
            time.sleep(min(delay, 8.0))

        assert response is not None
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

    def publications(
        self,
        start: str,
        end: str,
        modality: int = 6,
        page: int = 1,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "dataInicial": start.replace("-", ""),
            "dataFinal": end.replace("-", ""),
            "codigoModalidadeContratacao": modality,
            "pagina": page,
            "tamanhoPagina": 50,
        }
        if state:
            params["uf"] = state
        return self.get_list("/v1/contratacoes/publicacao", params)

    def purchase_items(
        self, cnpj: str, year: int, sequence: int
    ) -> list[dict[str, Any]]:
        return self.get_list(
            f"/v1/orgaos/{cnpj}/compras/{year}/{sequence}/itens",
            {"pagina": 1, "tamanhoPagina": 50},
        )


class ComprasGovClient(PublicApiClient):
    def __init__(self) -> None:
        super().__init__("https://dadosabertos.compras.gov.br")

    def practiced_material_prices(self, params: Mapping[str, str | int]) -> list[dict[str, Any]]:
        return self.get_list("/modulo-pesquisa-preco/1_consultarMaterial", params)

    def food_catalog(
        self, page: int = 1, class_code: int | None = None
    ) -> list[dict[str, Any]]:
        """CATMAT group 89 is the official group named 'Subsistência'."""
        params: dict[str, str | int] = {
            "pagina": page,
            "tamanhoPagina": 500,
            "codigoGrupo": 89,
            "statusItem": "true",
        }
        if class_code:
            params["codigoClasse"] = class_code
        return self.get_list(
            "/modulo-material/4_consultarItemMaterial",
            params,
        )

    def prices_for_catalog_item(
        self,
        catalog_item_code: int,
        *,
        state: str | None = None,
        municipality_code: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "pagina": 1,
            "tamanhoPagina": 50,
            "tipo": "codigoItemCatalogo",
            "codigo": catalog_item_code,
        }
        if state:
            params["estado"] = state
        if municipality_code:
            params["codigoMunicipio"] = municipality_code
        return self.practiced_material_prices(
            params
        )


class TransparencyClient(PublicApiClient):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Defina TRANSPARENCIA_API_KEY para consultar esta fonte.")
        super().__init__("https://api.portaldatransparencia.gov.br", api_key=api_key)

    def agreements(self, params: Mapping[str, str | int]) -> list[dict[str, Any]]:
        return self.get_list("/api-de-dados/convenios", params)
