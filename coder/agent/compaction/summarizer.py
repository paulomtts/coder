from pygents import ContextItem

from coder.agent.compaction.prompts import (
    SUMMARIZATION_SYSTEM_PROMPT, SUMMARIZATION_PROMPT,
    UPDATE_SUMMARIZATION_PROMPT,
)


def estimate_tokens(items: list[ContextItem]) -> int:
    total = 0
    for item in items:
        total += len(str(item.content)) // 4
    return total


def should_compact(items: list[ContextItem], threshold: float, max_context_tokens: int) -> bool:
    tokens = estimate_tokens(items)
    return tokens > threshold * max_context_tokens


def split_messages(items: list[ContextItem], keep_recent_tokens: int) -> tuple[list[ContextItem], list[ContextItem]]:
    recent_tokens = 0
    split_index = len(items)
    for i in range(len(items) - 1, -1, -1):
        item_tokens = len(str(items[i].content)) // 4
        if recent_tokens + item_tokens > keep_recent_tokens:
            split_index = i + 1
            break
        recent_tokens += item_tokens
    else:
        split_index = 0
    return list(items[:split_index]), list(items[split_index:])


async def run_compaction(toolkit, items, existing_summary, keep_recent_tokens):
    old_messages, recent_messages = split_messages(items, keep_recent_tokens)
    if not old_messages:
        return existing_summary or "", recent_messages
    conversation = "\n".join(
        f"[{item.content.get('role', 'unknown')}]: {item.content.get('content', str(item.content))}"
        for item in old_messages if isinstance(item.content, dict)
    )
    if existing_summary:
        prompt_template = "<previous-summary>\n{{ previous_summary }}\n</previous-summary>\n\n{{ conversation }}\n\n{{ update_prompt }}"
        response = await toolkit.chat(template=prompt_template, previous_summary=existing_summary, conversation=conversation, update_prompt=UPDATE_SUMMARIZATION_PROMPT, system=SUMMARIZATION_SYSTEM_PROMPT)
    else:
        prompt_template = "{{ conversation }}\n\n{{ summarize_prompt }}"
        response = await toolkit.chat(template=prompt_template, conversation=conversation, summarize_prompt=SUMMARIZATION_PROMPT, system=SUMMARIZATION_SYSTEM_PROMPT)
    return response.content, recent_messages
