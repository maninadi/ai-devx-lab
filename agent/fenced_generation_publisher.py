
from __future__ import annotations

from pathlib import Path

from agent.generation_fencing import GenerationFencing
from agent.recovery_generations import GenerationStore


class FencedGenerationPublisher:
    def __init__(
        self,
        *,
        checkpoint_root: Path,
        fencing_root: Path,
    ):
        self.store = GenerationStore(checkpoint_root)
        self.fencing = GenerationFencing(fencing_root)

    def publish(
        self,
        *,
        token: int,
        repo_root: Path,
        source_manifest,
        source_snapshot,
        source_checkpoint,
        source_memory,
        source_evidence,
    ):
        def action():
            return self.store.publish(
                repo_root,
                source_manifest,
                source_snapshot,
                source_checkpoint,
                source_memory,
                source_evidence,
            )

        return self.fencing.guarded(token, action)
