"""Unit tests for entity resolution fuzzy matching."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from agents.entity_resolution import EntityResolutionAgent


class MockTarget:
    def __init__(self, name, aliases=None):
        self.id = uuid4()
        self.name = name
        self.aliases = aliases or []


@pytest.mark.asyncio
async def test_fuzzy_resolves_exact():
    agent = EntityResolutionAgent()
    targets = [MockTarget("Rivian"), MockTarget("Lucid Motors")]
    all_names = ["rivian", "lucid motors"]
    name_to_target = {t.name.lower(): t for t in targets}

    result = await agent._resolve_one("Rivian", all_names, name_to_target, targets)
    assert result == targets[0].id


@pytest.mark.asyncio
async def test_fuzzy_resolves_partial():
    agent = EntityResolutionAgent()
    targets = [MockTarget("Rivian Automotive Inc")]
    all_names = ["rivian automotive inc"]
    name_to_target = {t.name.lower(): t for t in targets}

    result = await agent._resolve_one("Rivian", all_names, name_to_target, targets)
    assert result == targets[0].id


@pytest.mark.asyncio
async def test_no_match_returns_none_without_llm():
    agent = EntityResolutionAgent()
    targets = [MockTarget("Rivian")]
    all_names = ["rivian"]
    name_to_target = {"rivian": targets[0]}

    # "XYZ Corp" won't fuzzy-match above threshold, will try LLM and return None
    with patch.object(agent, "_llm_resolve", new_callable=AsyncMock, return_value=None):
        result = await agent._resolve_one("XYZ Corp", all_names, name_to_target, targets)
    assert result is None
