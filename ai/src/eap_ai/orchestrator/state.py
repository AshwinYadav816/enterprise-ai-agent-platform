"""Orchestrator state and the router's plan schema."""

from typing import Any, TypedDict

from pydantic import BaseModel, Field

from eap_ai.schemas import AgentName, AgentRequest


class Step(BaseModel):
    agent: AgentName
    instruction: str = Field(description="Self-contained instruction for this agent")
    uses_previous: bool = Field(
        default=False, description="True if this step needs the output of an earlier step"
    )


class Plan(BaseModel):
    steps: list[Step] = Field(description="1 to 3 steps, executed in order")
    reason: str = Field(default="", description="One short sentence explaining the plan")


class OrchestratorState(TypedDict):
    request: AgentRequest
    plan: Plan
    step_index: int
    outputs: list[dict[str, Any]]  # per step: result data, or {"agent", "error"}
    final_text: str
