"""LLM pipeline workflow — multi-agent orchestration.

Routes tasks to Claude, Codex, Gemini, and local Ollama models,
then synthesizes their responses. Supports several execution patterns:

- single: dispatch to one agent
- fan_out: dispatch to multiple agents in parallel, synthesize results
- chain: pipe output from one agent as input to the next
- debate: agents critique each other's responses iteratively
"""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.llm import Agent, AgentResponse, AgentTask, LLMActivities


class Strategy(StrEnum):
    SINGLE = "single"
    FAN_OUT = "fan_out"
    CHAIN = "chain"
    DEBATE = "debate"


@dataclass
class PipelineRequest:
    prompt: str
    system: str = ""
    strategy: Strategy = Strategy.FAN_OUT
    agents: list[Agent] = field(
        default_factory=lambda: [
            Agent.CLAUDE,
            Agent.CODEX,
            Agent.GEMINI,
        ]
    )
    debate_rounds: int = 2
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class PipelineResult:
    strategy: Strategy
    responses: list[AgentResponse]
    synthesis: AgentResponse | None = None


AGENT_DISPATCH = {
    Agent.CLAUDE: "dispatch_claude",
    Agent.CODEX: "dispatch_codex",
    Agent.GEMINI: "dispatch_gemini",
    Agent.OLLAMA: "dispatch_ollama",
}

TIMEOUT = timedelta(minutes=3)
RETRY = RetryPolicy(maximum_attempts=2)


@workflow.defn
class LLMPipelineWorkflow:
    """Orchestrate multi-agent LLM workflows with durable execution."""

    @workflow.run
    async def run(self, request: PipelineRequest) -> PipelineResult:
        match request.strategy:
            case Strategy.SINGLE:
                return await self._single(request)
            case Strategy.FAN_OUT:
                return await self._fan_out(request)
            case Strategy.CHAIN:
                return await self._chain(request)
            case Strategy.DEBATE:
                return await self._debate(request)

    async def _dispatch(
        self,
        agent: Agent,
        task: AgentTask,
    ) -> AgentResponse:
        """Dispatch a task to the appropriate agent activity."""
        activities = LLMActivities.__new__(LLMActivities)
        method = getattr(activities, AGENT_DISPATCH[agent])
        return await workflow.execute_activity_method(
            method,
            task,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

    async def _single(self, req: PipelineRequest) -> PipelineResult:
        """Send to one agent."""
        agent = req.agents[0]
        task = AgentTask(
            agent=agent,
            prompt=req.prompt,
            system=req.system,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        resp = await self._dispatch(agent, task)
        return PipelineResult(
            strategy=Strategy.SINGLE,
            responses=[resp],
        )

    async def _fan_out(self, req: PipelineRequest) -> PipelineResult:
        """Send to all agents in parallel, then synthesize."""
        tasks = []
        for agent in req.agents:
            task = AgentTask(
                agent=agent,
                prompt=req.prompt,
                system=req.system,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            tasks.append(self._dispatch(agent, task))

        responses: list[AgentResponse] = await asyncio.gather(*tasks)

        activities = LLMActivities.__new__(LLMActivities)
        synthesis = await workflow.execute_activity_method(
            activities.synthesize_responses,
            args=[responses, req.prompt],
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

        return PipelineResult(
            strategy=Strategy.FAN_OUT,
            responses=responses,
            synthesis=synthesis,
        )

    async def _chain(self, req: PipelineRequest) -> PipelineResult:
        """Pipe each agent's output as context to the next."""
        responses = []
        context = req.prompt

        for agent in req.agents:
            task = AgentTask(
                agent=agent,
                prompt=context,
                system=req.system,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            resp = await self._dispatch(agent, task)
            responses.append(resp)
            context = (
                f"Previous agent ({agent.value}) responded:\n{resp.content}\n\n"
                f"Original question: {req.prompt}\n\n"
                f"Build on or improve the previous response."
            )

        return PipelineResult(
            strategy=Strategy.CHAIN,
            responses=responses,
        )

    async def _debate(self, req: PipelineRequest) -> PipelineResult:
        """Agents critique each other's responses iteratively."""
        responses = []

        # Initial round — all agents answer independently
        initial = []
        for agent in req.agents:
            task = AgentTask(
                agent=agent,
                prompt=req.prompt,
                system=req.system,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            initial.append(self._dispatch(agent, task))

        round_responses: list[AgentResponse] = await asyncio.gather(*initial)
        responses.extend(round_responses)

        # Debate rounds — each agent critiques the others
        for round_num in range(req.debate_rounds):
            workflow.logger.info(f"Debate round {round_num + 1}")
            critiques = []
            for i, agent in enumerate(req.agents):
                others = [
                    f"{r.agent.value}: {r.content}" for j, r in enumerate(round_responses) if j != i
                ]
                critique_prompt = (
                    f"Original question: {req.prompt}\n\n"
                    f"Your previous answer: {round_responses[i].content}\n\n"
                    f"Other agents said:\n" + "\n---\n".join(others) + "\n\n"
                    "Critique the other responses and refine your answer."
                )
                task = AgentTask(
                    agent=agent,
                    prompt=critique_prompt,
                    system=req.system,
                    temperature=max(0.3, req.temperature - 0.1 * round_num),
                    max_tokens=req.max_tokens,
                )
                critiques.append(self._dispatch(agent, task))

            round_responses = await asyncio.gather(*critiques)
            responses.extend(round_responses)

        # Final synthesis
        activities = LLMActivities.__new__(LLMActivities)
        synthesis = await workflow.execute_activity_method(
            activities.synthesize_responses,
            args=[round_responses, req.prompt],
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

        return PipelineResult(
            strategy=Strategy.DEBATE,
            responses=responses,
            synthesis=synthesis,
        )
