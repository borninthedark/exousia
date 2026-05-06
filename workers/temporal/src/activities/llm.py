"""LLM pipeline activities — multi-agent orchestration.

Integrates three AI agents via their APIs:
- Claude (Anthropic API) — architecture, complex reasoning, code review
- Codex (OpenAI API) — code generation, implementation, refactoring
- Gemini (Google AI API) — documentation, research, analysis

Each agent can be dispatched as a Temporal activity with retries,
timeouts, and durable state tracking.
"""

from dataclasses import dataclass, field
from enum import StrEnum

import httpx
from temporalio import activity


class Agent(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class AgentConfig:
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"


@dataclass
class AgentTask:
    agent: Agent
    prompt: str
    system: str = ""
    context: dict[str, str] = field(default_factory=dict)
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class AgentResponse:
    agent: Agent
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMActivities:
    """Dispatch tasks to AI agents with durable execution."""

    def __init__(self, config: AgentConfig):
        self.config = config

    @activity.defn
    async def dispatch_claude(self, task: AgentTask) -> AgentResponse:
        """Send a task to Claude via the Anthropic API."""
        messages = [{"role": "user", "content": task.prompt}]
        body = {
            "model": self.config.anthropic_model,
            "max_tokens": task.max_tokens,
            "temperature": task.temperature,
            "messages": messages,
        }
        if task.system:
            body["system"] = task.system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        return AgentResponse(
            agent=Agent.CLAUDE,
            content=data["content"][0]["text"],
            model=data["model"],
            usage={
                "input_tokens": data["usage"]["input_tokens"],
                "output_tokens": data["usage"]["output_tokens"],
            },
        )

    @activity.defn
    async def dispatch_codex(self, task: AgentTask) -> AgentResponse:
        """Send a task to Codex/GPT via the OpenAI API."""
        messages = []
        if task.system:
            messages.append({"role": "system", "content": task.system})
        messages.append({"role": "user", "content": task.prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.openai_model,
                    "messages": messages,
                    "temperature": task.temperature,
                    "max_tokens": task.max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return AgentResponse(
            agent=Agent.CODEX,
            content=choice["message"]["content"],
            model=data["model"],
            usage=data.get("usage", {}),
        )

    @activity.defn
    async def dispatch_gemini(self, task: AgentTask) -> AgentResponse:
        """Send a task to Gemini via the Google AI API."""
        contents = [{"parts": [{"text": task.prompt}]}]
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": task.temperature,
                "maxOutputTokens": task.max_tokens,
            },
        }
        if task.system:
            body["systemInstruction"] = {"parts": [{"text": task.system}]}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta"
            f"/models/{self.config.google_model}:generateContent"
            f"?key={self.config.google_api_key}"
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})

        return AgentResponse(
            agent=Agent.GEMINI,
            content=text,
            model=self.config.google_model,
            usage={
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
            },
        )

    @activity.defn
    async def dispatch_ollama(self, task: AgentTask) -> AgentResponse:
        """Send a task to local Ollama (llama3.2 / qwen3)."""
        body = {
            "model": self.config.ollama_model,
            "prompt": task.prompt,
            "system": task.system,
            "stream": False,
            "options": {
                "temperature": task.temperature,
                "num_predict": task.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.config.ollama_url}/api/generate",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        return AgentResponse(
            agent=Agent.OLLAMA,
            content=data["response"],
            model=data["model"],
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
        )

    @activity.defn
    async def synthesize_responses(
        self,
        responses: list[AgentResponse],
        prompt: str,
    ) -> AgentResponse:
        """Use Claude to synthesize multiple agent responses into one."""
        summary = "\n\n".join(f"## {r.agent.value} ({r.model})\n{r.content}" for r in responses)
        synthesis_task = AgentTask(
            agent=Agent.CLAUDE,
            system=(
                "You are synthesizing responses from multiple AI agents. "
                "Combine their insights, resolve contradictions, and produce "
                "a single coherent response. Credit specific agents when their "
                "contribution is notable."
            ),
            prompt=f"Original question: {prompt}\n\nAgent responses:\n{summary}",
        )
        result: AgentResponse = await self.dispatch_claude(synthesis_task)
        return result
