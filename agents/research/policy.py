"""Static permissions and plan validation for the research agent."""

from collections.abc import Sequence

from agents.research.state import AgentToolCall


ALLOWED_TOOLS = frozenset(
    {
        "strategy_research",
        "comparison",
        "reporting",
    }
)
ALLOWED_STRATEGIES = frozenset({"moving_average", "momentum_regime"})


class AgentPolicyError(ValueError):
    """Raised when a planner requests a tool outside the static policy."""


def expected_plan(strategies: Sequence[str]) -> tuple[AgentToolCall, ...]:
    calls = [
        AgentToolCall("strategy_research", {"strategy_name": strategy})
        for strategy in strategies
    ]
    if len(strategies) > 1:
        calls.append(AgentToolCall("comparison", {}))
    calls.append(AgentToolCall("reporting", {}))
    return tuple(calls)


def authorize_plan(
    plan: Sequence[AgentToolCall],
    strategies: Sequence[str],
) -> tuple[AgentToolCall, ...]:
    requested = tuple(plan)
    for call in requested:
        if type(call) is not AgentToolCall:
            raise AgentPolicyError("Planner returned an invalid tool-call contract.")
        if not isinstance(call.name, str):
            raise AgentPolicyError("Tool names must be strings.")
        if call.name not in ALLOWED_TOOLS:
            raise AgentPolicyError(f"Tool is not permitted: {call.name!r}.")
        if (
            type(call.arguments) is not dict
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in call.arguments.items()
            )
        ):
            raise AgentPolicyError("Tool arguments must be plain string mappings.")
    expected = expected_plan(strategies)
    if requested != expected:
        raise AgentPolicyError(
            "Planner output does not match the permitted research workflow."
        )
    return requested
