"""Query Agent: ReAct-style NL query over the knowledge base (Sonnet)."""
import json
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from core.embeddings import embed
from core.llm import LLMClient, MODEL_SONNET
from db.models import get_session_factory
from db.queries import find_targets_by_name, get_latest_report, list_signals, semantic_search

log = structlog.get_logger()

MAX_ITERATIONS = 5

SYSTEM_PROMPT = """\
You are an intelligence analyst. Your job is to answer questions strictly from the signals \
in the database. Use the available tools to retrieve relevant data before answering.

Rules:
- When the user mentions a company, person, or topic by name, call resolve_target first to \
get the UUID. Use that UUID in all subsequent tool calls.
- Only report what the database contains. Do not supplement with general knowledge, \
training data, or anything not returned by a tool call.
- If the database has little or no data on a topic, say so plainly. Do not fill the gap \
with what you know about the subject from outside the database.
- Never speculate, infer, or extrapolate beyond what the signals explicitly state.
- Do not use emojis unless the user explicitly asks for them.
"""

TOOLS = [
    {
        "name": "resolve_target",
        "description": "Look up a target by name. Always call this first when the user mentions a company, person, or topic by name — you need the UUID to query signals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The target name to search for, e.g. 'New York Times'"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "semantic_search",
        "description": "Search signals using semantic similarity. Use for open-ended or concept queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 10},
                "target_id": {"type": "string", "format": "uuid", "description": "UUID of the target (e.g. '550e8400-e29b-41d4-a716-446655440000'). Must be a valid UUID, not a name."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "sql_query",
        "description": "Structured lookup of signals by target, date range, or signal type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "signal_type": {"type": "string", "enum": ["hiring", "research", "product", "funding", "mention"]},
                "days": {"type": "integer", "description": "Look back N days"},
                "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
                "limit": {"type": "integer", "default": 20},
            },
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
    {
        "name": "trigger_compare",
        "description": "Trigger a head-to-head comparison between two targets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_a_id": {"type": "string"},
                "target_b_id": {"type": "string"},
            },
            "required": ["target_a_id", "target_b_id"],
        },
    },
]


@dataclass
class QueryResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    iterations: int = 0


class QueryAgent:
    def __init__(self):
        self.llm = LLMClient()
        self._tool_results: list[str] = []
    
    def _parse_uuid(self, value: str | None, field: str = "target_id") -> UUID | None:
        if not value:
            return None
        try:
            return UUID(value)
        except ValueError:
            log.warning("invalid_uuid_from_model", field=field, value=value)
            return None  # or raise a ToolInputError if you want the agent to retry

    async def run(self, query: str) -> QueryResult:
        messages = [{"role": "user", "content": query}]
        iterations = 0

        for i in range(MAX_ITERATIONS):
            iterations = i + 1
            response = await self.llm.call(
                messages=messages,
                prompt="",  # unused when messages provided
                model=MODEL_SONNET,
                caller=f"query_agent:iteration_{i}",
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                tool_choice={"type": "auto"},
                max_tokens=2048,
            )

            # Append assistant turn
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                # Execute all tool calls and add results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._dispatch_tool(block.name, block.input)
                        self._tool_results.append(str(result)[:500])
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                messages.append({"role": "user", "content": tool_results})
        else:
            log.warning("query_agent_hit_max_iterations", query=query)

        # Extract final text answer
        answer = ""
        for block in response.content:
            if hasattr(block, "text"):
                answer = block.text
                break

        return QueryResult(
            answer=answer or "I was unable to find relevant information.",
            sources=self._tool_results,
            iterations=iterations,
        )

    async def _dispatch_tool(self, name: str, inputs: dict) -> object:
        session_factory = get_session_factory()

        if name == "resolve_target":
            async with session_factory() as session:
                targets = await find_targets_by_name(session, inputs["name"])
            if not targets:
                return {"error": f"No target found matching '{inputs['name']}'. It may not be tracked yet."}
            return [{"id": str(t.id), "name": t.name, "type": t.type} for t in targets]

        if name == "semantic_search":
            embedding = await embed(inputs["query"])
            target_id = self._parse_uuid(inputs.get("target_id"))
            async with session_factory() as session:
                signals = await semantic_search(
                    session, embedding, top_k=inputs.get("top_k", 10), target_id=target_id
                )
            return [
                {"summary": s.summary, "type": s.signal_type, "date": str(s.signal_date), "source": s.source}
                for s in signals
            ]

        if name == "sql_query":
            target_id = self._parse_uuid(inputs.get("target_id"))
            async with session_factory() as session:
                signals = await list_signals(
                    session,
                    target_id=target_id,
                    signal_type=inputs.get("signal_type"),
                    relevance=inputs.get("relevance"),
                    days=inputs.get("days"),
                    limit=inputs.get("limit", 20),
                )
            return [
                {"summary": s.summary, "type": s.signal_type, "date": str(s.signal_date), "relevance": s.relevance}
                for s in signals
            ]

        if name == "get_report":
            target_id = self._parse_uuid(inputs.get("target_id"))
            async with session_factory() as session:
                report = await get_latest_report(session, target_id, inputs["report_type"])
            return {"content": report.content if report else None}

        if name == "trigger_compare":
            from tasks.analyze import run_compare_task
            run_compare_task.apply_async(
                args=[inputs["target_a_id"], inputs["target_b_id"]],
                queue="llm",
            )
            return {"status": "comparison triggered"}

        return {"error": f"unknown tool: {name}"}
