"""Entity Resolution Agent: maps pending signals to tracked targets."""
import structlog
from rapidfuzz import process as fuzz_process
from uuid import UUID

from core.llm import LLMClient, MODEL_HAIKU
from db.models import Signal, Target

log = structlog.get_logger()

FUZZY_THRESHOLD = 85  # rapidfuzz score 0-100

LLM_RESOLVE_PROMPT = """\
You are resolving a company/entity name to a tracked target.

Entity mention: "{mention}"

Tracked targets (name | aliases):
{candidates}

Return the exact target name that best matches, or "NONE" if there is no good match.
Only return the name, nothing else.
"""


class EntityResolutionAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def resolve_all(
        self,
        pending_signals: list[Signal],
        targets: list[Target],
    ) -> dict[UUID, UUID | None]:
        """Returns {signal_id: target_id | None} for each pending signal."""
        if not targets or not pending_signals:
            return {}

        # Build name -> target map including aliases
        name_to_target: dict[str, Target] = {}
        for t in targets:
            name_to_target[t.name.lower()] = t
            for alias in (t.aliases or []):
                name_to_target[alias.lower()] = t

        all_names = list(name_to_target.keys())
        results: dict[UUID, UUID | None] = {}

        for signal in pending_signals:
            mention = self._extract_mention(signal)
            if not mention:
                results[signal.id] = None
                continue

            target_id = await self._resolve_one(mention, all_names, name_to_target, targets)
            results[signal.id] = target_id

        return results

    def _extract_mention(self, signal: Signal) -> str:
        """Extract the entity name to resolve from signal metadata."""
        meta = signal.metadata_ or {}
        mention = meta.get("entity_mention") or (signal.metadata_ or {}).get("source_item", "")
        return mention[:200]

    async def _resolve_one(
        self,
        mention: str,
        all_names: list[str],
        name_to_target: dict[str, Target],
        targets: list[Target],
    ) -> UUID | None:
        if not mention or not all_names:
            return None

        # Fuzzy match first
        result = fuzz_process.extractOne(mention.lower(), all_names, score_cutoff=FUZZY_THRESHOLD)
        if result:
            matched_name, score, _ = result
            log.info("entity_resolved_fuzzy", mention=mention, matched=matched_name, score=score)
            return name_to_target[matched_name].id

        # Fall back to LLM
        return await self._llm_resolve(mention, targets)

    async def _llm_resolve(self, mention: str, targets: list[Target]) -> UUID | None:
        candidates = "\n".join(
            f"{t.name} | {', '.join(t.aliases or [])}" for t in targets
        )
        try:
            response = await self.llm.call(
                prompt=LLM_RESOLVE_PROMPT.format(mention=mention, candidates=candidates),
                model=MODEL_HAIKU,
                caller="entity_resolution",
                max_tokens=64,
            )
            name = self.llm.extract_text(response).strip()
            if name == "NONE":
                return None
            # Find target by name
            for t in targets:
                if t.name.lower() == name.lower():
                    log.info("entity_resolved_llm", mention=mention, matched=t.name)
                    return t.id
        except Exception as e:
            log.warning("entity_resolution_llm_failed", mention=mention, error=str(e))
        return None
