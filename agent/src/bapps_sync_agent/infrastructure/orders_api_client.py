from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ClaimedOrderJob:
    job_id: str
    lease_token: str
    order: dict[str, Any]


class OrdersApiError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


class OrdersApiClient:
    def __init__(self, base_url: str, agent_code: str, token: str, timeout_seconds: int = 20) -> None:
        self._base_url = base_url.rstrip("/")
        self._agent_code = agent_code
        self._token = token
        self._timeout_seconds = timeout_seconds

    def claim(self, lease_seconds: int) -> ClaimedOrderJob | None:
        payload = self._request("POST", "/api/private/bapps-sync/v1/order-jobs/claim", {
            "lease_seconds": lease_seconds,
            "limit": 1,
        })
        job = payload.get("job")
        if job is None:
            return None
        if not isinstance(job, dict) or not isinstance(job.get("order"), dict):
            raise OrdersApiError("INVALID_ORDER_PAYLOAD", "La API devolvió un job inválido.", False)
        return ClaimedOrderJob(str(job["id"]), str(job["lease_token"]), job["order"])

    def complete(self, job: ClaimedOrderJob, result: dict[str, Any]) -> None:
        self._request("POST", f"/api/private/bapps-sync/v1/order-jobs/{job.job_id}/complete", {
            "lease_token": job.lease_token,
            **result,
        })

    def fail(self, job: ClaimedOrderJob, code: str, message: str, retryable: bool) -> None:
        self._request("POST", f"/api/private/bapps-sync/v1/order-jobs/{job.job_id}/fail", {
            "lease_token": job.lease_token,
            "error_code": code,
            "error_message": message[:1200],
            "retryable": retryable,
        })

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=encoded,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
                "X-BAPPS-Agent": self._agent_code,
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            retryable = exc.code in {408, 409, 425, 429} or exc.code >= 500
            raise OrdersApiError(f"ORDERS_API_HTTP_{exc.code}", detail or exc.reason, retryable) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OrdersApiError("ORDERS_API_UNAVAILABLE", str(exc), True) from exc
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrdersApiError("ORDERS_API_INVALID_JSON", "La API no devolvió JSON válido.", True) from exc
        if not isinstance(decoded, dict):
            raise OrdersApiError("ORDERS_API_INVALID_JSON", "La respuesta debe ser un objeto JSON.", True)
        return decoded
