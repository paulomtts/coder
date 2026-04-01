from pygents import ContextItem

SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.\n\nDo NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary."""

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.\n\nUse this EXACT format:\n\n## Goal\n[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]\n\n## Constraints & Preferences\n- [Any constraints, preferences, or requirements mentioned by user]\n- [Or "(none)" if none were mentioned]\n\n## Progress\n### Done\n- [x] [Completed tasks/changes]\n\n### In Progress\n- [ ] [Current work]\n\n### Blocked\n- [Issues preventing progress, if any]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale]\n\n## Next Steps\n1. [Ordered list of what should happen next]\n\n## Critical Context\n- [Any data, examples, or references needed to continue]\n- [Or "(none)" if not applicable]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.\n\nUpdate the existing structured summary with new information. RULES:\n- PRESERVE all existing information from the previous summary\n- ADD new progress, decisions, and context from the new messages\n- UPDATE the Progress section: move items from "In Progress" to "Done" when completed\n- UPDATE "Next Steps" based on what was accomplished\n- PRESERVE exact file paths, function names, and error messages\n- If something is no longer relevant, you may remove it\n\nUse this EXACT format:\n\n## Goal\n[Preserve existing goals, add new ones if the task expanded]\n\n## Constraints & Preferences\n- [Preserve existing, add new ones discovered]\n\n## Progress\n### Done\n- [x] [Include previously done items AND newly completed items]\n\n### In Progress\n- [ ] [Current work - update based on progress]\n\n### Blocked\n- [Current blockers - remove if resolved]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale] (preserve all previous, add new)\n\n## Next Steps\n1. [Update based on current state]\n\n## Critical Context\n- [Preserve important context, add new if needed]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

TURN_PREFIX_SUMMARIZATION_PROMPT = """This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained.\n\nSummarize the prefix to provide context for the retained suffix:\n\n## Original Request\n[What did the user ask for in this turn?]\n\n## Early Progress\n- [Key decisions and work done in the prefix]\n\n## Context for Suffix\n- [Information needed to understand the retained recent work]\n\nBe concise. Focus on what's needed to understand the kept suffix."""

BRANCH_SUMMARY_PROMPT = """Create a structured summary of this conversation branch for context when returning later.\n\nUse this EXACT format:\n\n## Goal\n[What was the user trying to accomplish in this branch?]\n\n## Constraints & Preferences\n- [Any constraints, preferences, or requirements mentioned]\n- [Or "(none)" if none were mentioned]\n\n## Progress\n### Done\n- [x] [Completed tasks/changes]\n\n### In Progress\n- [ ] [Work that was started but not finished]\n\n### Blocked\n- [Issues preventing progress, if any]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale]\n\n## Next Steps\n1. [What should happen next to continue this work]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

BRANCH_SUMMARY_PREAMBLE = """The user explored a different conversation branch before returning here.\nSummary of that exploration:\n"""


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
