"""
scraper/circular_detector.py
Tracks which circular URLs have already been seen, using a JSON file on disk.
"""
import json
from pathlib import Path

from loguru import logger

SEEN_FILE = Path("./data/raw/seen_circulars.json")


class CircularDetector:
    """Persistent tracker of seen circular URLs to avoid reprocessing."""

    def __init__(self, seen_file: str | Path = SEEN_FILE):
        self.seen_file = Path(seen_file)
        self.seen_file.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = self._load()

    def _load(self) -> set[str]:
        if self.seen_file.exists():
            try:
                data = json.loads(self.seen_file.read_text(encoding="utf-8"))
                return set(data.get("seen_urls", []))
            except Exception as e:
                logger.warning(f"Could not load seen_circulars.json: {e}")
        return set()

    def _save(self) -> None:
        self.seen_file.write_text(
            json.dumps({"seen_urls": list(self._seen)}, indent=2),
            encoding="utf-8",
        )

    def is_new(self, circular_url: str) -> bool:
        """Return True if this URL has NOT been seen before."""
        return circular_url not in self._seen

    def mark_as_seen(self, circular_url: str) -> None:
        """Mark a URL as seen and persist to disk."""
        self._seen.add(circular_url)
        self._save()

    def get_unseen(self, circulars_list: list[dict]) -> list[dict]:
        """Filter a list of circular dicts to only those with unseen URLs."""
        new_ones = [c for c in circulars_list if self.is_new(c["url"])]
        logger.info(
            f"{len(new_ones)} new circulars out of {len(circulars_list)} total"
        )
        return new_ones
