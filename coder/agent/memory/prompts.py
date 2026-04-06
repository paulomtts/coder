EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction assistant. You analyze conversation turns between a user and an AI coding assistant and extract durable facts worth remembering across sessions.

Focus on:
- User preferences (formatting, tools, coding style)
- Project conventions (naming, architecture, patterns)
- User role, expertise, and background
- Recurring project constraints

Do NOT extract:
- Ephemeral task details (what file is being edited right now)
- Information already in the existing memories
- Obvious facts derivable from the code itself"""

EXTRACTION_PROMPT = """## Existing Memories
{{ existing_memories }}

## Current Turn
{{ turn_content }}

## Current System Prompt Context
{{ system_context }}

Extract any user preferences, project facts, or conventions worth remembering long-term. Return a JSON array of objects with "topic" (slugified, e.g. "user-preferences") and "content" (the fact as a concise sentence or two). If a topic already exists in memories above, your content should merge old and new into a coherent replacement.

If there is nothing worth remembering, return exactly: nothing

Return ONLY the JSON array or "nothing". No other text."""

DECAY_SYSTEM_PROMPT = """You are a memory summarization assistant. You merge multiple session summaries into a single concise summary that preserves the most important information."""

DECAY_PROMPT = """Merge the following session summaries into a single concise summary. Preserve key decisions, important context, and significant events. Drop redundant details.

{{ entries }}

Return ONLY the merged summary as markdown text."""
