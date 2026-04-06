from coder.agent.memory.store import (
    MemoryEntry,
    read_entry,
    write_entry,
    delete_entry,
    list_entries,
    build_memory_index,
)


def test_write_and_read_semantic(tmp_path):
    entry = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers spaces over tabs.",
        tags=["preferences"],
    )
    write_entry(entry, base_dir=str(tmp_path))
    result = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))
    assert result is not None
    assert result.content == "Prefers spaces over tabs."
    assert result.type == "semantic"
    assert result.topic == "user-preferences"
    assert "preferences" in result.tags
    assert result.created is not None
    assert result.updated is not None


def test_write_overwrites_existing(tmp_path):
    entry1 = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers tabs.",
        tags=["preferences"],
    )
    write_entry(entry1, base_dir=str(tmp_path))
    first = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))

    entry2 = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers spaces.",
        tags=["preferences"],
    )
    write_entry(entry2, base_dir=str(tmp_path))
    second = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))

    assert second.content == "Prefers spaces."
    assert second.created == first.created  # preserves original created
    assert second.updated >= first.updated


def test_write_and_read_episodic(tmp_path):
    entry = MemoryEntry(
        type="episodic",
        topic="2026-04-06T14-30-00",
        content="Refactored the auth module.",
        tags=[],
    )
    write_entry(entry, base_dir=str(tmp_path))
    result = read_entry("episodic", "2026-04-06T14-30-00", base_dir=str(tmp_path))
    assert result is not None
    assert result.content == "Refactored the auth module."


def test_delete_entry(tmp_path):
    entry = MemoryEntry(
        type="semantic",
        topic="to-delete",
        content="Temporary.",
        tags=[],
    )
    write_entry(entry, base_dir=str(tmp_path))
    assert read_entry("semantic", "to-delete", base_dir=str(tmp_path)) is not None
    deleted = delete_entry("semantic", "to-delete", base_dir=str(tmp_path))
    assert deleted is True
    assert read_entry("semantic", "to-delete", base_dir=str(tmp_path)) is None


def test_delete_nonexistent(tmp_path):
    deleted = delete_entry("semantic", "nope", base_dir=str(tmp_path))
    assert deleted is False


def test_list_entries(tmp_path):
    for i in range(3):
        write_entry(
            MemoryEntry(
                type="semantic", topic=f"topic-{i}", content=f"Fact {i}", tags=[]
            ),
            base_dir=str(tmp_path),
        )
    entries = list_entries("semantic", base_dir=str(tmp_path))
    assert len(entries) == 3
    topics = {e.topic for e in entries}
    assert topics == {"topic-0", "topic-1", "topic-2"}


def test_list_entries_empty(tmp_path):
    entries = list_entries("semantic", base_dir=str(tmp_path))
    assert entries == []


def test_build_memory_index(tmp_path):
    write_entry(
        MemoryEntry(
            type="semantic", topic="prefs", content="Likes Python.", tags=["lang"]
        ),
        base_dir=str(tmp_path),
    )
    write_entry(
        MemoryEntry(
            type="semantic", topic="tools", content="Uses pytest.", tags=["testing"]
        ),
        base_dir=str(tmp_path),
    )
    index = build_memory_index(base_dir=str(tmp_path))
    assert "Likes Python." in index
    assert "Uses pytest." in index
