import json
import uuid

from datetime import datetime, timezone
from pathlib import Path


class RunTrace:
    """
    Append-only JSONL event recorder for one agent run.
    """

    def __init__(self, trace_dir: Path):
        self.run_id = uuid.uuid4().hex

        trace_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path = (
            trace_dir / f"{self.run_id}.jsonl"
        )

    def emit(self, event_type: str, **fields):
        event = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "run_id": self.run_id,
            "event": event_type,
            **fields,
        }

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(event) + "\n"
            )

        return event