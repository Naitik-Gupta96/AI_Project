# Hardening Report (feature/hardening-flash-talk)

Branch `feature/hardening-flash-talk`, starting from `feature/integration` at
`6c28593` (tag `pre-hardening-baseline`). Date: 2026-10-03.

**Verdict: ready for the flash talk**, based on the verification in section 10.

## 1. Repository audit

Read every source module, test, demo, prompt and markdown file. Baseline:
240 tests passed with 575 warnings (all `datetime.utcnow` deprecations). Every
demo, the experiment pipeline and the UI were run before any change.

## 2. Problems found

| # | Problem | Root cause | Impact | Severity | Fix |
|---|---|---|---|---|---|
| 1 | Same task reached CONSENSUS in one process and DEADLOCK in another | Agents chose options with Python's salted `hash()` | Demo not reproducible; "deterministic" claim false | High | Agents now decide through the provider; the mock is a pure function of the context |
| 2 | Agents bypassed `MockLLMProvider`, which had a second, unrelated mock | Mock logic duplicated inside each agent | No real provider abstraction; two mock systems | High | One pipeline: context → prompt → provider → parser → decision → message |
| 3 | Experiment outcomes were random draws | `random() < 0.5` decided deadlock, `random() < cf_fraction` decided recovery, events hard-coded | Results said nothing about the system | High | Each trial runs `pipeline.run_task`; synthetic results deleted; loader rejects the old format |
| 4 | REFUTE used with a prediction other than the standing proposal | No defined tag semantics for agents | Breaks the stance analysis behind consensus and deadlock | High | Semantics defined once (`PXPTag`, ARCHITECTURE.md) and enforced on model output |
| 5 | Counterfactual replay could diverge from the original | `HistoryEvent` dropped message metadata (e.g. a named alternative) | A pure replay was not faithful | Medium | `HistoryEvent` keeps metadata and is frozen; branches re-publish it |
| 6 | Prompts only loaded when run from the repo root | Relative file path | The prompt path silently fell back to a stub | Medium | Prompts are package data, read via `importlib.resources` |
| 7 | Run Viewer was a JSON dump; Analytics read the synthetic CSV | Prototype UI | Faculty would need to read JSON; charts showed fake data | Medium | UI rebuilt on typed views of real runs |
| 8 | Docs listed built components as FUTURE and contradicted each other | Status kept in many files | Misleading | Medium | One status table in README; other docs link to it |
| 9 | 575 deprecation warnings | `datetime.utcnow()` | Noise; future breakage | Low | Timezone-aware `utc_timestamp()` |
| 10 | `pytest` relied on `pythonpath = ["."]`; unused deps declared | Packaging drift | Tests could pass without a working install | Low | src layout and package data declared; tests use the installed package |
| 11 | UI said "Choose best option" for a different task | Hard-coded label | Inaccurate | Low | UI shows the real task text |

Two regressions introduced during this work were caught by clean-run
verification and fixed: `blackboard_demo.py` edited a now-frozen history event,
and the UI outcome block collapsed onto one line. `tests/test_examples.py` now
runs every example script.

## 3. Architecture changes

- `tasks.py`: `DecisionTask` with options and role-partitioned private evidence;
  the hand-written Flash Talk task; a seeded task generator.
- `pipeline.run_task`: the single end-to-end path used by the UI, the CLI demo
  and the experiment.
- `counterfactual/resolver.py`: counterfactual agents (reflection → intervention
  → branch → replay).
- `ui/`: typed views (`RunView`, `RunEvent`, `CounterfactualView`, `DemoView`,
  `ExperimentView`) built from real runs.
- Blackboard, PXP, scheduler, policies and the deadlock detector were kept; only
  the targeted fixes above were made.

## 4. Agent system

| Part | Status |
|---|---|
| Analyst | Opens with its best acceptable option by benefit score; refutes what its evidence rules out |
| Critic | Refutes constraint violations, citing them, without volunteering an alternative |
| Specialist | Adopts an alternative named in an objection if it passes its domain checks |
| Provider architecture | One interface (`LLMProvider.generate(LLMRequest) -> LLMResponse`) for every decision and reflection |
| Deterministic mock | `MockLLMProvider`: documented role rules; no hashing or randomness; labelled DETERMINISTIC MOCK everywhere |
| Local model | `OllamaProvider`, optional. One manual run with `qwen3:4b` completed end to end, but the model did not follow the specialist's resolver role, stayed deadlocked, and took about 3 minutes. Not used for any reported result |

## 5. Scheduler, deadlock, counterfactual

- **Scheduler and deadlock detector:** sound; unchanged. Deadlock has a written
  definition (Decision 16), and existing tests cover a single disagreement,
  thresholds, resolution, oscillation and REJECT.
- **Counterfactual engine:** metadata fix (problem 5). New tests cover branch
  isolation, an unmodified original, latest-first candidate order, infeasible
  tasks, invalid interventions, and replay failure (recorded as a FAILED branch,
  not raised).

## 6. Experiment pipeline

- **Real execution:** yes. Each trial runs Blackboard → three role agents →
  Scheduler → deadlock detector → (after a deadlock) reflection, branching and
  replay. Verified by instrumentation and by sabotage (section 10).
- **Synthetic:** the *tasks* only (procedurally generated, labelled as such).
  No outcome is simulated.
- **Pilot:** 100 tasks × 8 conditions (every subset of counterfactual-capable
  agents), seed 42. Counterfactual fraction is defined as k of the 3 agents
  being counterfactual-capable. Results and limits: [evaluation.md](evaluation.md).
- **Benchmarks:** planned only; none are integrated.

## 7. Frontend

Three tabs, all rendering typed views of real runs, with no business logic in Streamlit:

- **Flash Talk** shows task → agent timeline → DEADLOCK → reflection → original
  vs revised message → replay (inherited step dimmed, revision highlighted) →
  CONSENSUS → outcome, including a computed check that the original board was
  not modified. It runs on first load, so the screen is never empty.
- **Run Explorer** shows run metadata, a selectable timeline and per-event
  details for the Flash Talk task or any recorded pilot trial (re-executed live
  and checked against its record). Raw JSON is only in an expander.
- **Evaluation** shows methodology first, then results by fraction and by
  condition, then what is not measured.

## 8. Documentation

Rewritten: README (single status table), FLASH_TALK, ARCHITECTURE, TEAM, TASKS,
PROJECT, RESEARCH, and `docs/` agents_api, ui_api, shared_contract, evaluation,
proposal_summary, experiments/README. Targeted fixes: blackboard_api,
scheduler_api, counterfactual_api. Decision records 12-19 added. The obsolete
integration guide was removed.

A sweep for FUTURE, TODO, COMPLETE, VALIDATED, PROVES and IMPROVES finds only
benign uses: input validation, explicit negations, and future-work sections.
Every LLM and benchmark mention is a negation, qualified, or planned.

## 9. Test results

265 passed, 0 failed, 0 skipped, 0 warnings (about 6-20 s depending on the machine).

## 10. Verification (fresh clone of this branch, new virtualenv, `pip install -e ".[dev]"`)

| Check | Result |
|---|---|
| `python -m pytest` | 265 passed |
| `flash_talk_demo`, `scheduler_demo`, `agents_demo`, `blackboard_demo` | all exit 0 |
| Flash Talk demo in two processes, compared with `fc /b` | no differences (also identical under 3 `PYTHONHASHSEED` values) |
| `run_experiment.py` + `analyze_results.py` | 800 trials in 2.4 s; same numbers as [evaluation.md](evaluation.md) |
| Instrumentation (20-task pilot) | 788 agent actions = 600 original + 188 replayed messages; 912 provider calls = 788 actions + 124 reflections; 76 branches created and replayed by the engine; 1,552 deadlock checks; all equal to the recorded results |
| Sabotage: critic volunteers alternatives (in memory) | deadlock rate 0.45 → 0.40 and recovery shifts, so outcomes come from agent behaviour |
| `streamlit run frontend/app.py` | healthy in about 3.4 s; all tabs render (checked in a browser) |

## 11. Reproducibility

```bash
git clone <repo> && cd AI_Project && git checkout feature/hardening-flash-talk
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
python examples/flash_talk_demo.py
python -m streamlit run frontend/app.py
python experiments/run_experiment.py && python experiments/analyze_results.py
```

No internet access (after install), API key or model is needed.

## 12. Remaining limitations

- The agents are deterministic rules, not language models; the pilot numbers
  characterise the mechanism.
- Tasks are synthetic.
- No baselines or benchmarks yet.
- Local-model behaviour is uncharacterised (one anecdotal run).
- One intervention per branch, latest message first.
- The Blackboard is in memory only.

## 13-16. Flash talk

Demo sequence, what to say, safe claims, claims we must not make, and the
backup plan: [FLASH_TALK.md](../FLASH_TALK.md). One-sentence summary:

> We implemented a counterfactual replay mechanism and demonstrated recovery from
> a controlled deadlock scenario. We also built an end-to-end evaluation pipeline
> for further experimentation.

## 17. Git

Branch `feature/hardening-flash-talk`, based on `feature/integration`
(`6c28593`). Not pushed at the time of writing.
