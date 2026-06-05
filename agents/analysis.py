"""Analysis Agent: TrendAgent, SummaryAgent, CompareAgent (Sonnet)."""
from datetime import date, timedelta
from uuid import UUID

import structlog

from core.llm import LLMClient, MODEL_SONNET
from db.models import get_session_factory
from db.queries import create_report, get_latest_report, list_signals

log = structlog.get_logger()


class TrendAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def analyze(self, target_id: UUID, target_name: str) -> str:
        session_factory = get_session_factory()
        async with session_factory() as session:
            recent = await list_signals(session, target_id=target_id, days=30, limit=200)
            older = await list_signals(session, target_id=target_id, days=60, limit=200)

        # Compute frequency per signal type
        def freq(signals):
            counts: dict[str, int] = {}
            for s in signals:
                counts[s.signal_type] = counts.get(s.signal_type, 0) + 1
            return counts

        recent_freq = freq(recent)
        older_freq = freq(older)

        prompt = f"""Analyze signal frequency trends for "{target_name}".

Last 30 days signal counts: {recent_freq}
Previous 30 days signal counts: {older_freq}

Identify notable increases, decreases, or patterns. Write 2-3 bullet points.
"""
        response = await self.llm.call(
            prompt=prompt,
            model=MODEL_SONNET,
            caller="trend_agent",
            max_tokens=512,
        )
        return self.llm.extract_text(response)


class SummaryAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def summarize(self, target_id: UUID, target_name: str) -> str:
        session_factory = get_session_factory()
        async with session_factory() as session:
            signals = await list_signals(session, target_id=target_id, days=7, limit=50)

        if not signals:
            return f"No signals found for {target_name} in the past 7 days."

        signal_lines = "\n".join(
            f"[{s.signal_type}] {s.summary} ({s.signal_date or 'unknown date'})"
            for s in signals
        )

        prompt = f"""Write a concise weekly intelligence digest for "{target_name}".

Recent signals:
{signal_lines}

Write 3-5 sentences covering the most important developments. Be factual and specific.
"""
        response = await self.llm.call(
            prompt=prompt,
            model=MODEL_SONNET,
            caller="summary_agent",
            max_tokens=1024,
        )
        return self.llm.extract_text(response)


class CompareAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def compare(
        self,
        target_a_id: UUID,
        target_a_name: str,
        target_b_id: UUID,
        target_b_name: str,
        signal_type: str | None = None,
    ) -> str:
        session_factory = get_session_factory()
        async with session_factory() as session:
            sigs_a = await list_signals(
                session, target_id=target_a_id, signal_type=signal_type, days=30, limit=50
            )
            sigs_b = await list_signals(
                session, target_id=target_b_id, signal_type=signal_type, days=30, limit=50
            )

        def summarize_sigs(sigs):
            return "\n".join(
                f"[{s.signal_type}/{s.relevance}] {s.summary}" for s in sigs[:20]
            ) or "(no signals)"

        prompt = f"""Compare "{target_a_name}" and "{target_b_name}" on recent intelligence signals.

{target_a_name} signals (last 30 days):
{summarize_sigs(sigs_a)}

{target_b_name} signals (last 30 days):
{summarize_sigs(sigs_b)}

Write a head-to-head comparison covering:
1. Hiring activity
2. Product/research signals
3. Overall momentum
Keep it to 4-6 bullet points total.
"""
        response = await self.llm.call(
            prompt=prompt,
            model=MODEL_SONNET,
            caller="compare_agent",
            max_tokens=1024,
        )
        return self.llm.extract_text(response)


class AnalysisAgent:
    """Wraps all analysis sub-agents and persists reports."""

    def __init__(self):
        self.trend = TrendAgent()
        self.summary = SummaryAgent()
        self.compare = CompareAgent()

    async def run_daily(self, target_id: UUID, target_name: str) -> None:
        session_factory = get_session_factory()

        trend_content = await self.trend.analyze(target_id, target_name)
        summary_content = await self.summary.summarize(target_id, target_name)

        async with session_factory() as session:
            await create_report(session, {
                "target_id": target_id,
                "report_type": "trend",
                "content": trend_content,
            })
            await create_report(session, {
                "target_id": target_id,
                "report_type": "weekly_digest",
                "content": summary_content,
            })
        log.info("analysis_daily_complete", target_id=str(target_id))

    async def run_compare(
        self,
        target_a_id: UUID,
        target_a_name: str,
        target_b_id: UUID,
        target_b_name: str,
    ) -> str:
        content = await self.compare.compare(target_a_id, target_a_name, target_b_id, target_b_name)
        session_factory = get_session_factory()
        async with session_factory() as session:
            await create_report(session, {
                "target_id": target_a_id,
                "report_type": "comparison",
                "content": content,
            })
        return content
