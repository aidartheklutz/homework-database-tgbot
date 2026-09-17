import json
from pathlib import Path


class EditorRepository:
    def __init__(self, path: Path):
        self.path = path

    def list_ids(self) -> frozenset[int]:
        if not self.path.exists():
            return frozenset()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            values = data.get("sest1", []) if isinstance(data, dict) else []
            return frozenset(int(value) for value in values)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return frozenset()

    def add(self, user_id: int) -> bool:
        editor_ids = set(self.list_ids())
        if user_id in editor_ids:
            return False
        editor_ids.add(user_id)
        self._save(editor_ids)
        return True

    def remove(self, user_id: int) -> bool:
        editor_ids = set(self.list_ids())
        if user_id not in editor_ids:
            return False
        editor_ids.remove(user_id)
        self._save(editor_ids)
        return True

    def _save(self, editor_ids: set[int]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps({"sest1": sorted(editor_ids)}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
