"""Query Agent: orchestrates SemanticSearchAgent, SQLAgent, and SummaryAgent."""
import json
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from core.llm import LLMClient, MODEL_SONNET
from db.models import get_session_factory
from db.queries import find_targets_by_name, get_latest_report
from agents.subagents import SemanticSearchAgent, SQLAgent, SummaryAgent

log = structlog.get_logger()

MAX_ITERATIONS = 6

SYSTEM_PROMPT = """\
You are an intelligence orchestrator. Your job is to answer a user's question by delegating to \
specialized retrieval agents and then synthesizing their results.

Available tools:
- resolve_target: always call this first when the user mentions a company, person, or topic by \
  name — you need the UUID to pass to retrieval agents.
- invoke_semantic_search: best for open-ended concept queries ("what is X doing with Y", \
  "recent activity around Z"). Pass the original query and the resolved target_id.
- invoke_sql_lookup: best for structured or filtered queries ("hiring signals past 30 days", \
  "high-relevance product signals"). Pass the original query and the resolved target_id.
- get_report: fetch a pre-generated analysis report for a target.

Rules:
- When the user mentions a name, call resolve_target first.
- For most queries, call both invoke_semantic_search and invoke_sql_lookup to maximize coverage.
- Never answer from your own knowledge — only from tool results.
- If the retrieved data is sparse, say so plainly.
- Do not use emojis unless the user explicitly asks for them.
"""

TOOLS = [
    {
        "name": "resolve_target",
        "description": "Look up a target by name. Always call this first when the user mentions a company, person, or topic by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The target name to search for"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "invoke_semantic_search",
        "description": "Run a semantic similarity search over signals. Best for open-ended or concept queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "target_id": {"type": "string", "format": "uuid", "description": "UUID of the target"},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "invoke_sql_lookup",
        "description": "Run a structured SQL lookup of signals. Best for filtered queries (by type, date range, or relevance).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language description of what to filter for"},
                "target_id": {"type": "string", "format": "uuid", "description": "UUID of the target"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_report",
        "description": "Fetch the latest analysis report for a target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "report_type": {"type": "string", "enum": ["weekly_digest", "trend", "comparison"]},
            },
            "required": ["target_id", "report_type"],
        },
    },
]


@dataclass
class QueryResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    iterations: int = 0


class QueryAgent:
    """Orchestrator: routes queries to specialized subagents, synthesizes with SummaryAgent."""

    def __init__(self):
        self.llm = LLMClient()
        self._gathered_signals: list[dict] = []

    def _parse_uuid(self, value: str | None, field: str = "target_id") -> UUID | None:
        if not value:
            return None
        try:
            return UUID(value)
        except ValueError:
            log.warning("invalid_uuid_from_model", field=field, value=value)
            return None

    async def run(self, query: str) -> QueryResult:
        messages = [{"role": "user", "content": query}]
        iterations = 0
        response = None

        for i in range(MAX_ITERATIONS):
            iterations = i + 1
            response = await self.llm.call(
                messages=messages,
                prompt="",
                model=MODEL_SONNET,
                caller=f"query_orchestrator:iteration_{i}",
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                tool_choice={"type": "auto"},
                max_tokens=2048,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._dispatch(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                messages.append({"role": "user", "content": tool_results})
        else:
            log.warning("query_orchestrator_hit_max_iterations", query=query)

        # Synthesize gathered signals into a final answer via SummaryAgent
        if self._gathered_signals:
            answer = await SummaryAgent().run(query, self._gathered_signals)
        else:
            # Fall back to whatever text the orchestrator produced
            answer = ""
            if response:
                for block in response.content:
                    if hasattr(block, "text"):
                        answer = block.text
                        break
            answer = answer or "No relevant signals found in the database for this query."

        return QueryResult(
            answer=answer,
            sources=self._gathered_signals[:5],
            iterations=iterations,
        )

    async def _dispatch(self, name: str, inputs: dict) -> object:
        session_factory = get_session_factory()

        if name == "resolve_target":
            async with session_factory() as session:
                targets = await find_targets_by_name(session, inputs["name"])
            if not targets:
                return {"error": f"No target found matching '{inputs['name']}'. It may not be tracked yet."}
            return [{"id": str(t.id), "name": t.name, "type": t.type} for t in targets]

        if name == "invoke_semantic_search":
            target_id = self._parse_uuid(inputs.get("target_id"))
            signals = await SemanticSearchAgent().run(
                query=inputs["query"],
                target_id=target_id,
                top_k=inputs.get("top_k", 10),
            )
            self._gathered_signals.extend(signals)
            log.info("semantic_search_agent_done", signal_count=len(signals))
            return {"signals_found": len(signals), "preview": signals[:3]}

        if name == "invoke_sql_lookup":
            target_id = self._parse_uuid(inputs.get("target_id"))
            signals = await SQLAgent().run(
                query=inputs["query"],
                target_id=target_id,
            )
            # Deduplicate by summary before extending
            existing = {s["summary"] for s in self._gathered_signals}
            new_signals = [s for s in signals if s["summary"] not in existing]
            self._gathered_signals.extend(new_signals)
            log.info("sql_agent_done", signal_count=len(signals), new=len(new_signals))
            return {"signals_found": len(signals), "preview": signals[:3]}

        if name == "get_report":
            target_id = self._parse_uuid(inputs.get("target_id"))
            async with session_factory() as session:
                report = await get_latest_report(session, target_id, inputs["report_type"])
            return {"content": report.content if report else None}

        return {"error": f"unknown tool: {name}"}
