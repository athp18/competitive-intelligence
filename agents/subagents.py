"""Specialized subagents for the query pipeline."""
import json
from uuid import UUID

import structlog

from core.embeddings import embed
from core.llm import LLMClient, MODEL_SONNET, MODEL_HAIKU
from db.models import get_session_factory
from db.queries import list_signals, semantic_search

log = structlog.get_logger()


def _signals_to_dicts(signals) -> list[dict]:
    return [
        {
            "summary": s.summary,
            "type": s.signal_type,
            "date": str(s.signal_date),
            "source": s.source,
            "relevance": s.relevance,
        }
        for s in signals
    ]


class SemanticSearchAgent:
    """Reformulates the user query for semantic search, then retrieves matching signals."""

    SYSTEM = """\
You are a semantic search specialist. Your job is to rewrite a user query into the best possible \
search phrase for retrieving relevant signals from a vector database. The database contains \
intelligence signals about companies, people, and topics — things like hiring trends, product \
launches, research publications, funding events, and mentions.

Return only the reformulated search phrase as plain text, nothing else. No preamble, no explanation.
"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(
        self,
        query: str,
        target_id: UUID | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        # Reformulate query for better vector retrieval
        response = await self.llm.call(
            prompt=query,
            model=MODEL_HAIKU,
            caller="semantic_search_agent:reformulate",
            system=self.SYSTEM,
            max_tokens=128,
        )
        reformulated = ""
        for block in response.content:
            if hasattr(block, "text"):
                reformulated = block.text.strip()
                break
        search_query = reformulated or query
        log.info("semantic_agent_reformulated", original=query, reformulated=search_query)

        embedding = await embed(search_query)
        session_factory = get_session_factory()
        async with session_factory() as session:
            signals = await semantic_search(
                session, embedding, top_k=top_k, target_id=target_id
            )
        return _signals_to_dicts(signals)


class SQLAgent:
    """Extracts structured filters from a query, then retrieves matching signals via SQL."""

    SYSTEM = """\
You are a structured query specialist. Given a natural language query about intelligence signals, \
extract the appropriate filters as JSON. The available filters are:

- signal_type: one of [hiring, research, product, funding, mention] — only set if the query clearly \
  refers to one type
- days: integer look-back window (e.g. 30 for "past month") — only set if a time window is mentioned
- relevance: one of [high, medium, low] — only set if explicitly mentioned
- limit: integer (default 20)

Return only valid JSON with these keys. Omit any key that should not be filtered on.
Example: {"signal_type": "hiring", "days": 30, "limit": 20}
"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(
        self,
        query: str,
        target_id: UUID | None = None,
    ) -> list[dict]:
        response = await self.llm.call(
            prompt=query,
            model=MODEL_HAIKU,
            caller="sql_agent:extract_filters",
            system=self.SYSTEM,
            max_tokens=128,
        )
        filters: dict = {}
        try:
            filters = self.llm.extract_json(response) or {}
            if not isinstance(filters, dict):
                filters = {}
        except Exception:
            pass
        log.info("sql_agent_filters", filters=filters)

        session_factory = get_session_factory()
        async with session_factory() as session:
            signals = await list_signals(
                session,
                target_id=target_id,
                signal_type=filters.get("signal_type"),
                relevance=filters.get("relevance"),
                days=filters.get("days"),
                limit=filters.get("limit", 20),
            )
        return _signals_to_dicts(signals)


class SummaryAgent:
    """Synthesizes signals gathered by other agents into a final answer."""

    SYSTEM = """\
You are an intelligence analyst. You will be given a user question and a collection of signals \
retrieved from a database. Synthesize a direct answer using only the provided signals.

Format:
- Start with a short markdown heading (## Target: Topic) summarizing the query.
- Use bullet points for all findings. No prose paragraphs.
- Each bullet should be one concise sentence.
- If signals are sparse or duplicated, note it briefly after the bullets.

Rules:
- Do not use emojis unless the user explicitly asks for them.
"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, original_query: str, signals: list[dict]) -> str:
        if not signals:
            return "No relevant signals found in the database for this query."

        signals_text = json.dumps(signals, indent=2, default=str)
        prompt = f"Question: {original_query}\n\nSignals:\n{signals_text}"

        response = await self.llm.call(
            prompt=prompt,
            model=MODEL_SONNET,
            caller="summary_agent:synthesize",
            system=self.SYSTEM,
            max_tokens=1024,
        )
        for block in response.content:
            if hasattr(block, "text"):
                return block.text.strip()
        return "Unable to synthesize an answer from the available signals."
