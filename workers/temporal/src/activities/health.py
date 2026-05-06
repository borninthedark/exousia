"""Health check activities — deep service verification."""

from dataclasses import dataclass

import httpx
from temporalio import activity


@dataclass
class ServiceTarget:
    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] | None = None
    expected_status: list[int] | None = None
    expected_body: str | None = None


@dataclass
class HealthResult:
    name: str
    healthy: bool
    status_code: int | None = None
    response_ms: float = 0
    error: str | None = None


SERVICES: list[ServiceTarget] = [
    ServiceTarget("forgejo", "http://forgejo:3000/api/v1/version"),
    ServiceTarget(
        "paperless",
        "http://paperless:8000/api/",
        headers={"Host": "paperless.exousia.local"},
        expected_status=[200, 302, 401],
    ),
    ServiceTarget("temporal", "http://temporal-server:7233/api/v1/system-info"),
    ServiceTarget("authelia", "http://authelia:9091/api/health"),
    ServiceTarget("ollama", "http://ollama:11434/api/tags"),
    ServiceTarget("open-webui", "http://open-webui:8080/health"),
    ServiceTarget("registry", "http://registry:5000/v2/"),
    ServiceTarget("changedetection", "http://changedetection:5000"),
    ServiceTarget("dashy", "http://dashy:8080"),
    ServiceTarget("caddy", "http://caddy:80", expected_status=[200, 301, 302, 308]),
]


class HealthActivities:
    """Deep health checks beyond simple TCP connectivity."""

    @activity.defn
    async def check_service(self, target: ServiceTarget) -> HealthResult:
        """HTTP health check with response validation."""
        expected = target.expected_status or [200]
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=False,
            ) as client:
                resp = await client.request(
                    target.method,
                    target.url,
                    headers=target.headers or {},
                )

                healthy = resp.status_code in expected
                if healthy and target.expected_body:
                    healthy = target.expected_body in resp.text

                return HealthResult(
                    name=target.name,
                    healthy=healthy,
                    status_code=resp.status_code,
                    response_ms=resp.elapsed.total_seconds() * 1000,
                )
        except Exception as e:
            return HealthResult(
                name=target.name,
                healthy=False,
                error=str(e),
            )

    @activity.defn
    async def check_ollama_models(self) -> HealthResult:
        """Verify expected models are loaded in Ollama."""
        expected_models = {"qwen3:8b", "llama3.2:1b"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("http://ollama:11434/api/tags")
                resp.raise_for_status()
                loaded = {m["name"] for m in resp.json().get("models", [])}
                missing = expected_models - loaded
                if missing:
                    return HealthResult(
                        name="ollama-models",
                        healthy=False,
                        error=f"missing models: {missing}",
                    )
                return HealthResult(name="ollama-models", healthy=True)
        except Exception as e:
            return HealthResult(name="ollama-models", healthy=False, error=str(e))

    @activity.defn
    async def send_alert(self, results: list[HealthResult]) -> None:
        """Send SMTP alert for unhealthy services via Paperless/Authelia SMTP."""
        unhealthy = [r for r in results if not r.healthy]
        if not unhealthy:
            return

        body = "Unhealthy services:\n\n"
        for r in unhealthy:
            body += f"  - {r.name}: status={r.status_code} error={r.error}\n"

        activity.logger.warning(body)
        # TODO: wire to SMTP via aiosmtplib using Proton Mail creds
