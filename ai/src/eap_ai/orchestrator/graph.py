"""LangGraph orchestration: router -> execute_step (loop) -> synthesize (only for >1 step).

Nodes publish our Event dicts through LangGraph's custom stream writer; service.run consumes
them with `astream(stream_mode="custom")`.
"""

import logging
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from eap_ai import llm
from eap_ai.agents import chat, document, email, meeting, report, research
from eap_ai.agents.base import (
    UNTRUSTED_NOTE,
    Agent,
    AgentContext,
    AgentInputError,
    format_prior_outputs,
    prior_output_text,
    status_event,
)
from eap_ai.orchestrator.router import make_plan
from eap_ai.orchestrator.state import OrchestratorState
from eap_ai.schemas import AgentName, Event

log = logging.getLogger(__name__)

AGENTS: dict[AgentName, Agent] = {
    AgentName.research: research.run,
    AgentName.email: email.run,
    AgentName.meeting: meeting.run,
    AgentName.report: report.run,
    AgentName.document: document.run,
    AgentName.chat: chat.run,
}

SYNTH_SYSTEM = f"""You write the final short reply after several assistant steps ran for the \
user. The full results are already shown to the user as cards, so do NOT repeat them. In at most \
120 words: say what was done, point out anything important (e.g. unassigned action items, \
missing information), and mention any step that failed. Use only the step outputs given. \
{UNTRUSTED_NOTE}"""


def _emit(event: Event) -> None:
    get_stream_writer()(event.model_dump())


def _ok(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for o in outputs if "error" not in o]


def _final_text(output: dict[str, Any]) -> str:
    """Readable text of a single step's result, used as the answer when there is one step."""
    if "error" in output:
        return str(output["error"])
    out = output.get("output", {})
    if output.get("agent") == AgentName.email.value:
        return f"Subject: {out.get('subject', '')}\n\n{out.get('body', '')}"
    if output.get("agent") in (AgentName.meeting.value, AgentName.document.value):
        return str(out.get("summary", ""))
    return prior_output_text(output)


async def router_node(state: OrchestratorState) -> dict[str, Any]:
    _emit(status_event("Planning…"))
    plan = await make_plan(state["request"])
    _emit(status_event("Plan: " + " → ".join(s.agent.value for s in plan.steps)))
    return {"plan": plan, "step_index": 0, "outputs": [], "final_text": ""}


async def execute_step_node(state: OrchestratorState) -> dict[str, Any]:
    plan, i = state["plan"], state["step_index"]
    step = plan.steps[i]
    outputs = list(state["outputs"])
    _emit(
        Event(
            type="agent",
            data={
                "name": step.agent.value,
                "step": i + 1,
                "total": len(plan.steps),
                "instruction": step.instruction,
            },
        )
    )

    if step.uses_previous and len(_ok(outputs)) < len(outputs):
        message = f"Skipped the {step.agent.value} step because an earlier step failed."
        _emit(Event(type="error", data={"agent": step.agent.value, "message": message}))
        outputs.append({"agent": step.agent.value, "error": message})
        return {"outputs": outputs, "step_index": i + 1}

    ctx = AgentContext(
        request=state["request"], instruction=step.instruction, prior_outputs=_ok(outputs)
    )
    result: dict[str, Any] | None = None
    try:
        async for event in AGENTS[step.agent](ctx):
            if event.type == "result":
                result = event.data
            _emit(event)
        if result is None:
            raise RuntimeError(f"{step.agent.value} agent produced no result")
        outputs.append(result)
    except Exception as exc:
        if isinstance(exc, AgentInputError):
            message = str(exc)
        else:
            log.exception("Agent %s failed", step.agent.value)
            message = f"The {step.agent.value} step failed. Please try again."
        _emit(Event(type="error", data={"agent": step.agent.value, "message": message}))
        outputs.append({"agent": step.agent.value, "error": message})

    update: dict[str, Any] = {"outputs": outputs, "step_index": i + 1}
    if len(plan.steps) == 1:
        update["final_text"] = _final_text(outputs[-1])
    return update


async def synthesize_node(state: OrchestratorState) -> dict[str, Any]:
    _emit(status_event("Wrapping up…"))
    outputs = state["outputs"]
    failed = [f"- {o['agent']}: {o['error']}" for o in outputs if "error" in o]
    parts = [f"User request: {state['request'].query}", format_prior_outputs(_ok(outputs))]
    if failed:
        parts.append("Failed steps:\n" + "\n".join(failed))
    messages = [
        SystemMessage(content=SYNTH_SYSTEM),
        HumanMessage(content="\n\n".join(p for p in parts if p)),
    ]
    text: list[str] = []
    async for chunk in llm.get_chat_model("smart", streaming=True).astream(messages):
        if isinstance(chunk.content, str) and chunk.content:
            text.append(chunk.content)
            _emit(Event(type="token", data={"text": chunk.content}))
    return {"final_text": "".join(text)}


def _after_step(state: OrchestratorState) -> str:
    total = len(state["plan"].steps)
    if state["step_index"] < total:
        return "execute_step"
    return "synthesize" if total > 1 else END


@lru_cache
def build_graph() -> CompiledStateGraph:
    g = StateGraph(OrchestratorState)
    g.add_node("router", router_node)
    g.add_node("execute_step", execute_step_node)
    g.add_node("synthesize", synthesize_node)
    g.add_edge(START, "router")
    g.add_edge("router", "execute_step")
    g.add_conditional_edges("execute_step", _after_step, ["execute_step", "synthesize", END])
    g.add_edge("synthesize", END)
    return g.compile()
