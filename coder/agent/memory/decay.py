from datetime import datetime, timedelta, timezone

from coder.agent.memory.prompts import DECAY_PROMPT, DECAY_SYSTEM_PROMPT
from coder.agent.memory.store import (
    DEFAULT_MEMORY_DIR,
    MemoryEntry,
    delete_entry,
    list_entries,
    write_entry,
)


def group_by_age(
    entries: list[MemoryEntry], now: datetime | None = None
) -> tuple[list[MemoryEntry], list[MemoryEntry], list[MemoryEntry]]:
    if now is None:
        now = datetime.now(timezone.utc)

    recent: list[MemoryEntry] = []
    to_weekly: list[MemoryEntry] = []
    to_monthly: list[MemoryEntry] = []

    for entry in entries:
        # Skip already-decayed entries
        if entry.decay:
            continue

        created = entry.created or now
        age = now - created

        if age < timedelta(days=7):
            recent.append(entry)
        elif age < timedelta(days=30):
            to_weekly.append(entry)
        else:
            to_monthly.append(entry)

    return recent, to_weekly, to_monthly


def _week_key(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"week-{year}-W{week:02d}"


def _month_key(dt: datetime) -> str:
    return f"month-{dt.year}-{dt.month:02d}"


async def _merge_group(
    toolkit,
    entries: list[MemoryEntry],
    key_fn,
    decay_label: str,
    base_dir: str,
) -> None:
    if not entries:
        return

    # Group entries by their target key (week or month)
    groups: dict[str, list[MemoryEntry]] = {}
    for entry in entries:
        created = entry.created or datetime.now(timezone.utc)
        key = key_fn(created)
        groups.setdefault(key, []).append(entry)

    for key, group in groups.items():
        entries_text = "\n\n---\n\n".join(f"### {e.topic}\n{e.content}" for e in group)

        response = await toolkit.chat(
            template=DECAY_PROMPT,
            entries=entries_text,
            system=DECAY_SYSTEM_PROMPT,
        )

        write_entry(
            MemoryEntry(
                type="episodic",
                topic=key,
                content=response.content,
                tags=[],
                decay=decay_label,
            ),
            base_dir=base_dir,
        )

        for entry in group:
            delete_entry("episodic", entry.topic, base_dir)


async def run_decay(
    toolkit,
    base_dir: str = DEFAULT_MEMORY_DIR,
    now: datetime | None = None,
) -> None:
    entries = list_entries("episodic", base_dir)
    if not entries:
        return

    _, to_weekly, to_monthly = group_by_age(entries, now=now)

    await _merge_group(toolkit, to_weekly, _week_key, "weekly", base_dir)
    await _merge_group(toolkit, to_monthly, _month_key, "monthly", base_dir)
