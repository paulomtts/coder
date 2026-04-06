import json
from dataclasses import dataclass

from coder.agent.memory.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_PROMPT


@dataclass
class SemanticFact:
    topic: str
    content: str


async def extract_semantic_facts(
    toolkit, turn_content: str, existing_memories: str, system_context: str
) -> list[SemanticFact]:
    response = await toolkit.chat(
        template=EXTRACTION_PROMPT,
        turn_content=turn_content,
        existing_memories=existing_memories or "(none)",
        system_context=system_context or "(none)",
        system=EXTRACTION_SYSTEM_PROMPT,
    )

    text = response.content.strip()
    if text.lower() == "nothing":
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    facts = []
    for item in data:
        if isinstance(item, dict) and "topic" in item and "content" in item:
            facts.append(SemanticFact(topic=item["topic"], content=item["content"]))
    return facts
