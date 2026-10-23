"""Router: turns a request into a short plan of agent steps (fast model, structured output)."""

import logging

from eap_ai.agents.base import ask
from eap_ai.orchestrator.state import Plan, Step
from eap_ai.schemas import AgentName, AgentRequest

log = logging.getLogger(__name__)

MAX_STEPS = 3
ROUTER_HISTORY_MESSAGES = 4
HISTORY_SNIPPET_CHARS = 300

ROUTER_SYSTEM = """You are the planner of a company AI assistant. Choose which agents to run, \
in order, to fulfil the user's request. Use as FEW steps as possible (1 is typical, max 3).

Agents:
- research: answer a question from the user's uploaded company documents (with citations).
- document: summarize/analyze the specific documents the user selected (needs selected documents).
- meeting: summarize a meeting transcript: decisions, action items, open questions \
(needs an attached transcript or an earlier step's text).
- email: draft, rewrite, fix grammar, change tone, or summarize an email thread.
- report: write a weekly, monthly, sprint or project report.
- chat: greetings, small talk, thanks, or questions about the assistant itself. No documents.

Rules:
- Each instruction must be self-contained (the agent does not see the other steps).
- Set uses_previous=true when a step needs an earlier step's output.
- Any request for information (facts, rules, how-to, explanations, numbers) -> research, \
even if it sounds like general knowledge. chat is ONLY for greetings, thanks, small talk, or \
questions about what this assistant can do.
- Write instructions in the user's language and keep their specifics (names, dates, tone).

Examples:
Request: "How many vacation days do employees get?"
-> [research: "How many vacation days do employees get?"]

Request: "Summarize this meeting and email the action items to the team" (transcript attached)
-> [meeting: "Summarize the attached meeting transcript with decisions and action items",
    email (uses_previous): "Draft an email to the team listing the meeting's action items \
with owners and due dates"]

Request: "hi, how are you?"
-> [chat: "Reply to the greeting"]

Request: "How should containers be run?"
-> [research: "How should containers be run according to company policy?"]

Request: "Summarize this file" (2 documents selected)
-> [document: "Summarize the selected documents"]

Request: "Write a sprint report on the mobile app and email it to my manager"
-> [report: "Write a sprint report on the mobile app",
    email (uses_previous): "Draft an email to my manager sharing the sprint report"]"""


def _router_message(req: AgentRequest) -> str:
    has_transcript = bool(req.transcript and req.transcript.strip())
    lines = [
        f"Transcript attached: {'yes' if has_transcript else 'no'}",
        f"Selected documents: {len(req.doc_ids or [])}",
    ]
    if req.history:
        recent = req.history[-ROUTER_HISTORY_MESSAGES:]
        lines.append("Recent conversation:")
        lines += [f"{m.role}: {m.content[:HISTORY_SNIPPET_CHARS]}" for m in recent]
    lines.append(f"\nRequest: {req.query}")
    return "\n".join(lines)


def _fallback(req: AgentRequest) -> Plan:
    return Plan(steps=[Step(agent=AgentName.research, instruction=req.query)], reason="fallback")


async def make_plan(req: AgentRequest) -> Plan:
    """Plan for a request. force_agent skips the LLM; routing failures fall back to research."""
    if req.force_agent is not None:
        step = Step(agent=req.force_agent, instruction=req.query)
        return Plan(steps=[step], reason=f"forced: {req.force_agent.value}")
    try:
        plan = await ask("router", Plan, ROUTER_SYSTEM, _router_message(req))
    except Exception:
        log.exception("Router failed; falling back to research")
        return _fallback(req)
    steps = [s for s in plan.steps if s.instruction.strip()][:MAX_STEPS]
    if not steps:
        return _fallback(req)
    steps[0].uses_previous = False  # nothing precedes the first step
    return Plan(steps=steps, reason=plan.reason)
