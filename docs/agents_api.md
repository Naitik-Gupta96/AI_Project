# Agents API

`ai_project.agents`, `ai_project.llm`, `ai_project.tasks`.

## Quick start

```python
from ai_project.agents import build_team
from ai_project.blackboard import Blackboard
from ai_project.tasks import flash_talk_task

task = flash_talk_task()
board = Blackboard()
board.initialize_task(task.question, task.board_metadata())   # question + option names only

analyst, critic, specialist = build_team(task)                # default: MockLLMProvider
message = analyst.act(board)       # PXPMessage; the Scheduler normally publishes it
board.publish_message(message)
```

## Tasks and evidence (`ai_project.tasks`)

| Type | Fields |
|---|---|
| `Evidence` | `scores: {option: float}` (preference, higher is better), `objections: {option: reason}` |
| `DecisionTask` | `task_id`, `question`, `options`, `evidence: {role: Evidence}` |

`DecisionTask.feasible_options()` (no role objects) and `best_feasible()`
(highest analyst score among those) are ground truth for experiments; agents
never see other roles' evidence. `flash_talk_task()` is the demo task;
`generate_tasks(n, seed, n_options=3, objection_rate=0.3)` builds synthetic
tasks deterministically.

## The decision pipeline (`BaseAgent`)

```
act(board):  build_context(board) -> decide(context) -> AgentDecision.to_pxp_message(...)
decide(ctx): render_prompt(ctx) -> provider.generate(LLMRequest(prompt, ctx))
             -> parser.parse(text) -> _normalize(decision, ctx)
reflect(task, options, history, own_event) -> AgentDecision | None
```

| Type | Role |
|---|---|
| `AgentContext` | what the agent sees: `agent_id, role, task, options, evidence, status, iteration, proposal, history, reflect_on` |
| `AgentDecision` | what it decides: `tag, prediction, explanation, confidence, metadata` (validated on construction) |
| `PXPMessage` | what is published (see [blackboard_api.md](blackboard_api.md)) |

Constructor: `AnalystAgent(agent_id=None, llm_provider=None, evidence=None, parser=None)`
(same for `CriticAgent`, `SpecialistAgent`). `agent.usage` counts provider
calls and the tokens the provider reported (`None` if it reported none).

**Normalization** keeps model output within PXP semantics and records every
repair in `metadata["normalized"]`: a REFUTE of a non-standing option becomes a
REFUTE of the standing proposal naming that option as `alternative`; a RATIFY of
a different option becomes REVISE; an option name embedded in longer text is
mapped to the option; an unknown option raises `AgentError`. The deterministic
mock never triggers these repairs.

Errors: provider failures and unparseable output raise `AgentError`; the
Scheduler turns that into a FAILED run with the error in its trace.

## Roles

| Role | Forward behaviour (mock rules) | Reflection after a deadlock |
|---|---|---|
| analyst | opens with its best acceptable option; refutes proposals its evidence rules out; otherwise ratifies | if its opening proposal was later refuted: open with its best unrefuted option instead |
| critic | refutes proposals that break a constraint it knows, citing it, **without naming an alternative**; otherwise ratifies | if it refuted without an alternative: same refutation, naming its best unrefuted acceptable option |
| specialist | if the latest objection names an alternative it accepts, REVISE to it; otherwise refutes or ratifies by its domain evidence | if it refuted or ratified a later-refuted option: REVISE to its best unrefuted acceptable option instead |

The exact rules are in the docstring of `llm/mock.py`. Reflection uses only
the agent's own evidence and what the run made public.

## Providers (`ai_project.llm`)

```python
class LLMProvider(ABC):
    name: str
    deterministic: bool
    def generate(self, request: LLMRequest) -> LLMResponse: ...   # LLMResponse(text, usage)
    def is_available(self) -> bool: ...
    def describe(self) -> dict: ...                                # recorded with results
```

| Provider | What it is |
|---|---|
| `MockLLMProvider` | **Deterministic mock.** Applies the role rules to `request.context`; ignores the prompt text, which carries the same information. No hashing, no randomness, no token usage. |
| `OllamaProvider(model="qwen3:4b", host=..., seed=0, temperature=0.0)` | **Local model.** Sends `request.prompt` to Ollama with JSON output, temperature 0 and a seed; reports token counts. Optional; not labelled deterministic. |

To add a provider, subclass `LLMProvider`, return the JSON schema in
`llm/prompts/act.md` (or `{"no_change": true, ...}` for reflection prompts),
and pass it to `build_team(task, provider)` or `run_task(..., provider=...)`.

## Prompts

`src/ai_project/llm/prompts/` (shipped as package data): `act.md` and
`reflect.md` frames, plus `analyst.md`, `critic.md`, `specialist.md` role
instructions. They are `string.Template` files (`$task`, `$evidence`,
`$history`, ...). `agent.render_prompt(context)` shows exactly what a model would see;
`python examples/agents_demo.py --show-prompt` prints them.

## Parser

`AgentDecisionParser.parse(text)` extracts the JSON object (markdown fences
tolerated), checks required fields (`tag`, `prediction`, `explanation`,
`confidence` in [0, 1]) and returns an `AgentDecision`, raising `ParseError`
otherwise. `parse_reflection(text)` returns `None` for `{"no_change": true}`.
