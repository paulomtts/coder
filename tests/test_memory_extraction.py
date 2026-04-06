import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from coder.agent.memory.extraction import extract_semantic_facts, SemanticFact


@pytest.mark.asyncio
async def test_extract_returns_facts():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = json.dumps(
        [{"topic": "user-preferences", "content": "Prefers spaces over tabs."}]
    )
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(
        toolkit, "user: please use spaces not tabs", "", ""
    )
    assert len(facts) == 1
    assert isinstance(facts[0], SemanticFact)
    assert facts[0].topic == "user-preferences"
    assert facts[0].content == "Prefers spaces over tabs."


@pytest.mark.asyncio
async def test_extract_returns_empty_on_nothing():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "nothing"
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(toolkit, "hello", "", "")
    assert facts == []


@pytest.mark.asyncio
async def test_extract_handles_malformed_json():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "not valid json at all"
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(toolkit, "hello", "", "")
    assert facts == []
