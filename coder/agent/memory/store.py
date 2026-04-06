import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml


DEFAULT_MEMORY_DIR = os.path.expanduser("~/.coder/memory")


@dataclass
class MemoryEntry:
    type: str  # "semantic" or "episodic"
    topic: str  # filename stem (e.g. "user-preferences" or "2026-04-06T14-30-00")
    content: str  # markdown body
    tags: list[str] = field(default_factory=list)
    created: datetime | None = None
    updated: datetime | None = None
    decay: str | None = None  # "weekly" or "monthly" for merged episodic entries


def _entry_path(memory_type: str, topic: str, base_dir: str) -> str:
    return os.path.join(base_dir, memory_type, f"{topic}.md")


def write_entry(entry: MemoryEntry, base_dir: str = DEFAULT_MEMORY_DIR) -> None:
    path = _entry_path(entry.type, entry.topic, base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    now = datetime.now(timezone.utc)

    # Preserve original created timestamp if file exists;
    # otherwise use entry.created if provided, else now
    existing = read_entry(entry.type, entry.topic, base_dir)
    created = existing.created if existing else (entry.created or now)
    updated = now

    frontmatter = {
        "type": entry.type,
        "created": created.isoformat(),
        "updated": updated.isoformat(),
        "tags": entry.tags,
    }
    if entry.decay:
        frontmatter["decay"] = entry.decay

    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, default_flow_style=False))
        f.write("---\n\n")
        f.write(entry.content)
        f.write("\n")


def read_entry(
    memory_type: str, topic: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> MemoryEntry | None:
    path = _entry_path(memory_type, topic, base_dir)
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Parse YAML frontmatter
    if not text.startswith("---"):
        return MemoryEntry(type=memory_type, topic=topic, content=text)

    parts = text.split("---", 2)
    if len(parts) < 3:
        return MemoryEntry(type=memory_type, topic=topic, content=text)

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    created = None
    if "created" in meta:
        created = datetime.fromisoformat(meta["created"])
    updated = None
    if "updated" in meta:
        updated = datetime.fromisoformat(meta["updated"])

    return MemoryEntry(
        type=meta.get("type", memory_type),
        topic=topic,
        content=body,
        tags=meta.get("tags", []),
        created=created,
        updated=updated,
        decay=meta.get("decay"),
    )


def delete_entry(
    memory_type: str, topic: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> bool:
    path = _entry_path(memory_type, topic, base_dir)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def list_entries(
    memory_type: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> list[MemoryEntry]:
    dir_path = os.path.join(base_dir, memory_type)
    if not os.path.isdir(dir_path):
        return []
    entries = []
    for name in sorted(os.listdir(dir_path)):
        if name.endswith(".md"):
            topic = name[:-3]
            entry = read_entry(memory_type, topic, base_dir)
            if entry:
                entries.append(entry)
    return entries


def build_memory_index(base_dir: str = DEFAULT_MEMORY_DIR) -> str:
    entries = list_entries("semantic", base_dir)
    if not entries:
        return ""
    parts = []
    for entry in entries:
        parts.append(f"### {entry.topic}\n{entry.content}")
    return "\n\n".join(parts)
