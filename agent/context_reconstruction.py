
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from agent.checkpoint import CheckpointStore, RecoveryBlocked
from agent.context import ContextPolicy, ToolContextBudget
from agent.evidence import read_file_range
from agent.evidence_ledger import EvidenceLedger
from agent.run_recovery import (
    RunSnapshotStore,
    validate_recovery_boundary,
)
from agent.working_memory import (
    InvalidMemoryCapsule,
    MemoryCapsule,
    MemoryCapsuleStore,
)


@dataclass
class LocalContextAudit:
    run_id: str
    response_id: str
    turn: int
    evidence_ledger: EvidenceLedger
    context_budget: ToolContextBudget

    # This report never authorizes model execution.
    model_resume_allowed: bool = False


def compaction_advice(capsule: MemoryCapsule) -> str:
    """Advisory only; never modifies provider conversation state."""
    capsule.validate()

    if capsule.pressure == "exhausted":
        return "finalize_or_stop"

    if capsule.pressure == "high" or capsule.omitted_evidence:
        return "manual_review"

    return "monitor"


def reconstruct_local_context(
    repo_root: Path,
    snapshot_store: RunSnapshotStore,
    checkpoint_store: CheckpointStore,
    memory_store: MemoryCapsuleStore,
    *,
    context_policy: ContextPolicy,
) -> LocalContextAudit:
    """Audit local evidence at a safe boundary; never resume a model."""

    snapshot = snapshot_store.load()

    # Reuse the Day 20 recovery boundary gate.
    validate_recovery_boundary(snapshot, checkpoint_store)

    try:
        capsule = memory_store.load()
    except (InvalidMemoryCapsule, OSError, UnicodeError) as exc:
        raise RecoveryBlocked(
            "Memory capsule unavailable or invalid"
        ) from exc

    # All durable records must describe the same boundary.
    if (
        capsule.run_id,
        capsule.response_id,
        capsule.turn,
    ) != (
        snapshot.run_id,
        snapshot.response_id,
        snapshot.turn,
    ):
        raise RecoveryBlocked(
            "Memory capsule boundary mismatch"
        )

    if (
        capsule.context_chars_limit
        != context_policy.max_total_tool_chars
    ):
        raise RecoveryBlocked(
            "Context policy differs from saved capsule"
        )

    # Day 22 keeps only a bounded number of references.
    # Missing references prevent full index reconstruction.
    if capsule.omitted_evidence:
        raise RecoveryBlocked(
            "Capsule omitted evidence; full index unavailable"
        )

    ledger = EvidenceLedger()
    seen = set()

    for item in capsule.recent_evidence:
        if (
            not isinstance(item.path, str)
            or not item.path
            or type(item.start_line) is not int
            or type(item.end_line) is not int
            or not isinstance(item.sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", item.sha256) is None
        ):
            raise RecoveryBlocked(
                "Malformed saved evidence reference"
            )

        key = (
            item.path,
            item.start_line,
            item.end_line,
            item.sha256,
        )

        if key in seen:
            raise RecoveryBlocked(
                "Duplicate saved evidence reference"
            )

        seen.add(key)

        # Use the existing safe repository-read implementation.
        result = read_file_range(
            repo_root=repo_root,
            path=item.path,
            start_line=item.start_line,
            end_line=item.end_line,
        )

        if (
            result.get("ok") is not True
            or result.get("path") != item.path
            or result.get("start_line") != item.start_line
            or result.get("end_line") != item.end_line
        ):
            raise RecoveryBlocked(
                "Saved evidence range is no longer readable"
            )

        digest = hashlib.sha256(
            result["content"].encode("utf-8")
        ).hexdigest()

        if digest != item.sha256:
            raise RecoveryBlocked(
                "Saved evidence changed since observation"
            )

        if not ledger.record(
            "read_file_range",
            result,
            truncated=False,
        ):
            raise RecoveryBlocked(
                "Cannot reconstruct verified evidence"
            )

    # Reconstruct the saved local character counter.
    # This is NOT the provider's model token count.
    budget = ToolContextBudget(context_policy)
    budget.used_chars = capsule.context_chars_used

    return LocalContextAudit(
        run_id=snapshot.run_id,
        response_id=snapshot.response_id,
        turn=snapshot.turn,
        evidence_ledger=ledger,
        context_budget=budget,
    )
