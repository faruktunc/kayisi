import json
from pathlib import Path

from app.domain.literature.model import Observation


class JsonLiteratureRepository:
    """Literatür gözlemlerini data/literature.json dosyasından okur."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is None:
            with self._path.open(encoding="utf-8") as fh:
                self._cache = json.load(fh)
        return self._cache

    def studies(self) -> list[dict]:
        return list(self._load()["studies"])

    def observations(self) -> list[Observation]:
        return [Observation(**o) for o in self._load()["observations"]]
