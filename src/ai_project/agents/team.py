"""Builds the team for a task from the prompt matrix (one agent per role of the task's domain)."""

from collections.abc import Callable, Mapping

from ai_project.agents.base import Agent, Tool
from ai_project.benchmarks.base import Task
from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider
from ai_project.llm.usage import UsageMeter

ToolFactory = Callable[[Task, str], Mapping[str, Tool]]


def build_team(
    task: Task,
    provider: LLMProvider,
    usage: UsageMeter | None = None,
    tools: ToolFactory | None = None,
    max_tool_calls: int = 0,
    max_retries: int = 1,
) -> list[Agent]:
    """
    Args:
        task: The task; ``task.domain`` selects the personas
        provider: Shared decision provider
        usage: Shared usage meter (created if omitted)
        tools: ``tools(task, role)`` returns the tools for that role
        max_tool_calls: Tool calls per turn
        max_retries: Extra attempts after a parse or grammar error
    """
    usage = usage or UsageMeter()
    specs = prompts.roles(task.domain)
    team = tuple(spec.role for spec in specs)
    return [
        Agent(
            agent_id=spec.role,
            role=spec.role,
            task=task,
            provider=provider,
            persona=spec.persona,
            team=team,
            max_retries=max_retries,
            tools=tools(task, spec.role) if tools else None,
            max_tool_calls=max_tool_calls,
            usage=usage,
        )
        for spec in specs
    ]
