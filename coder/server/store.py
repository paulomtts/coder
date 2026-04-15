from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from coder.server.protocol import SessionRecord


class SessionStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def save(self, record: SessionRecord) -> None:
        path = self._path(record.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = record.model_dump(mode="json")

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp_path = Path(tmp.name)

        os.replace(tmp_path, path)

    def load(self, session_id: str) -> SessionRecord | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        return SessionRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[SessionRecord]:
        records: list[SessionRecord] = []
        for path in self.base_dir.glob("*.json"):
            try:
                records.append(
                    SessionRecord.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue
        records.sort(key=lambda r: r.updated_at, reverse=True)
        return records
