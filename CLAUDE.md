# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Research agent using LangGraph's StateGraph for workflow orchestration with human-in-the-loop. Uses Alibaba Cloud DashScope's Qwen3.5-plus model via OpenAI-compatible API. Supports LangSmith tracing, Phoenix observability, A/B testing, and Guardrails security. System prompts and CLI are in Chinese.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the LangGraph research agent (interactive)
python -m src.main "AI"

# Run pytest suite (38+ tests in tests/)
pytest tests/ -v
pytest tests/test_nodes.py -v              # single test file
pytest tests/test_nodes.py::TestPlannerJsonParsing::test_parse_clean_json  # single test

# Run evaluation system (all 30 topics)
python evals/runners/daily_eval.py
python evals/runners/daily_eval.py --limit 5  # limit topics
python evals/runners/daily_eval.py --output-dir evals/reports  # custom output dir
python evals/runners/daily_eval.py --dataset evals/datasets/topics.json  # custom dataset

# Run A/B comparison test
python ab_test.py "AI"

# Run guardrails tests (standalone scripts, not pytest)
python test_guardrails_fix.py
python test_sql_injection.py
python test_rce_guardrails.py
python test_xss_guardrails.py
python test_path_traversal.py

# Legacy ReAct agent
python simple_react.py
```

## Architecture

**Core LangGraph Workflow** (linear pipeline with interrupts):
```
planner → [interrupt] → researcher → writer → [interrupt] → saver
```

**Three execution paths** — This is critical to understand when modifying `main.py`:
- **Happy path (approve):** Uses the compiled LangGraph with `interrupt_before=["researcher", "saver"]` and `MemorySaver` checkpointer. Resumes via `Command(resume="continue")`.
- **Modify path:** Bypasses the graph entirely — calls `planner_node`, `researcher_node`, `writer_node`, `saver_node` as plain functions. The graph's interrupt/resume mechanism is not used for modifications.
- **Eval path:** `daily_eval.py` compiles a separate graph with `interrupt_before=[]` and sets `user_feedback: "auto"` to skip all human interaction and output guardrails.
- **A/B test path:** `ab_test.py` also bypasses the graph — calls nodes directly as functions, passing `llm=` parameter to planner and writer for model switching.

**Key Files:**
- `src/main.py` - CLI entry point; manages two interrupt cycles with approve/modify logic
- `src/graph.py` - StateGraph definition with `interrupt_before=["researcher", "saver"]`
- `src/nodes.py` - 4 nodes (planner, researcher, writer, saver), all `@traceable`. Nodes apply `clean_state_strings()` for Windows surrogate character handling. DashScope `BadRequestError` (content filter) is caught in planner and writer with user-friendly error states. Output guardrails skipped when `user_feedback == "auto"`.
- `src/state.py` - `ResearchState(TypedDict)` with fields: topic, messages (uses `add_messages` reducer), research_steps, sources, report_draft, final_markdown_path, user_feedback, error_message
- `src/config.py` - LLM config via `get_llm()` factory, LangSmith/Phoenix setup, A/B testing config
- `src/tools.py` - `search_tool` (DuckDuckGo, no API key), `calculator_tool` (AST-based safe eval, NOT `eval()`), `save_markdown_tool` (writes to `outputs/`)

**Production Components:**
- `evals/` - Evaluation system with LLM-as-judge. Uses a single combined LLM call per topic for 4 metrics: faithfulness, relevance, source_accuracy, coverage. Citation quality uses pure string matching (no LLM). Overall score = faithfulness×0.35 + relevance×0.35 + source_accuracy×0.30. 30 Chinese test topics in `evals/datasets/topics.json`.
- `ab_test.py` - A/B testing; quality scoring is heuristic-based (length, headers, structure), not LLM-based. Reports saved to `evals/reports/`.
- `.github/workflows/daily_eval.yml` - GitHub Actions daily eval at 08:00 UTC. Requires `DASHSCOPE_API_KEY` and `LANGCHAIN_API_KEY` secrets.
- `src/guardrails/rails.py` - Regex-based input/output security checks (~80 patterns). Logs to `logs/guardrails_logs/`. Broad patterns like shell metacharacters have false-positive risk.

## API Configuration

Environment variables from `config.env`:
- `DASHSCOPE_API_KEY` — required, Alibaba Cloud DashScope
- `LANGCHAIN_API_KEY` — optional, for LangSmith tracing (note: this is `LANGCHAIN_API_KEY`, not `LANGSMITH_API_KEY`)
- `LANGCHAIN_PROJECT` — default "research-agent"
- `LANGCHAIN_TRACING_V2` — default "true"
- `AB_TEST_PROMPT_VERSION` — "A" or "B"
- `AB_TEST_MODEL_A` / `AB_TEST_MODEL_B` — model names for A/B testing (default: "qwen3.5-plus")
- `PHOENIX_ENDPOINT` — optional, Phoenix observability endpoint (e.g. `http://localhost:6006/v1/traces`). Phoenix is disabled by default; set `DISABLE_PHOENIX=0` and provide `PHOENIX_ENDPOINT` to enable.

DuckDuckGo is used for web search (no API key required). `config.env` may contain vestigial keys (TAVILY_API_KEY, COHERE_API_KEY) that are not used by the current code.

## Notes

- Reports saved to `outputs/{topic}_report.md`
- Windows compatibility: extensive UTF-8 surrogate character handling throughout nodes and main
- Test scripts are standalone (run with `python`, not `pytest`) — they use `_check_patterns` directly from guardrails
- `conftest.py` autouse fixture sets `DASHSCOPE_API_KEY=test-key-for-unit-tests` and disables LangSmith tracing for all pytest tests
- `simple_react.py` is a legacy pre-LangGraph ReAct loop for comparison
- Researcher node runs up to 2 concurrent searches via `ThreadPoolExecutor` (was sequential with 3s delay)

## Gstack

Use the `/browse` skill from gstack for all web browsing. NEVER use `mcp__claude-in-chrome__*` tools.

Available skills:
`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`

If gstack skills aren't working, run `cd .claude/skills/gstack && ./setup` to build the binary and register skills.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
