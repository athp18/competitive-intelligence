"""Smoke tests for extraction helpers (no LLM calls)."""
from agents.extraction import _item_to_text, _batch_items


def test_item_to_text_picks_relevant_fields():
    item = {
        "title": "Company launches product",
        "description": "A new product was launched",
        "irrelevant": "ignore this",
    }
    text = _item_to_text(item)
    assert "Company launches product" in text
    assert "A new product" in text
    assert "ignore this" not in text


def test_batch_items_respects_max_chars():
    items = [{"title": "x" * 1000, "description": "y" * 1000}] * 10
    batches = _batch_items(items, max_chars=3000)
    assert len(batches) > 1
    for batch in batches:
        assert len(batch) >= 1


def test_batch_items_single_small():
    items = [{"title": "small"} for _ in range(5)]
    batches = _batch_items(items, max_chars=10000)
    assert len(batches) == 1
    assert len(batches[0]) == 5
