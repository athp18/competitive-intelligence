#!/usr/bin/env python3
"""Seed the DB with demo targets for portfolio demos."""
import asyncio
import uuid

from db.models import get_session_factory
from db.queries import create_target

DEMO_TARGETS = [
    {
        "id": uuid.uuid4(),
        "name": "Rivian",
        "type": "company",
        "aliases": ["Rivian Automotive", "RIVN"],
        "sources": {
            "github": {"org": "rivian"},
            "greenhouse": {"slug": "rivian"},
            "lever": {"slug": "rivian"},
            "news": {"query": "Rivian electric vehicle"},
            "hn": {"query": "Rivian", "include_hiring": True},
        },
        "schedule": {"github": "daily", "news": "6h", "hn": "6h", "greenhouse": "daily"},
    },
    {
        "id": uuid.uuid4(),
        "name": "Lucid Motors",
        "type": "company",
        "aliases": ["Lucid Group", "LCID"],
        "sources": {
            "greenhouse": {"slug": "lucidmotors"},
            "lever": {"slug": "lucidmotors"},
            "news": {"query": "Lucid Motors electric vehicle"},
            "hn": {"query": "Lucid Motors", "include_hiring": False},
        },
        "schedule": {"news": "6h", "greenhouse": "daily"},
    },
]


async def seed():
    session_factory = get_session_factory()
    async with session_factory() as session:
        for data in DEMO_TARGETS:
            target = await create_target(session, data)
            print(f"Created: {target.name} ({target.id})")


if __name__ == "__main__":
    asyncio.run(seed())
