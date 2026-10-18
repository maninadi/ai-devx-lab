from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent.evidence_ledger import EvidenceLedger


class FinalStatus(StrEnum):
    CITED = "cited"
    ABSTAINED = "abstained"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class FinalReview:
    status: FinalStatus
    accepted: bool
    reason: str


def tool_choice_for_turn(
    turn: int,
    max_turns: int,
) -> str:
    """
    Reserve the final model turn for an answer.

    This bounds tool-using turns, but does not
    guarantee that the model produces usable text.
    """

    if (
        max_turns < 1
        or turn < 1
        or turn > max_turns
    ):
        raise ValueError("Invalid turn configuration")

    if turn == max_turns:
        return "none"

    if turn == 1:
        return "required"

    return "auto"


def review_final_answer(
    answer: str,
    ledger: EvidenceLedger,
) -> FinalReview:
    """
    Enforce one of two final-answer formats:

    1. One or more cited bullet claims.
    2. A single explicit ABSTAIN statement.

    This checks citation provenance, not
    semantic correctness.
    """

    lines = [
        line.strip()
        for line in answer.splitlines()
        if line.strip()
    ]

    if not lines:
        return FinalReview(
            status=FinalStatus.UNVERIFIED,
            accepted=False,
            reason="Empty final answer",
        )

    # Explicit abstention is a legitimate outcome.
    if (
        len(lines) == 1
        and lines[0].startswith("ABSTAIN:")
    ):
        explanation = lines[0][len("ABSTAIN:"):].strip()

        if len(explanation) < 15:
            return FinalReview(
                status=FinalStatus.UNVERIFIED,
                accepted=False,
                reason="Abstention lacks explanation",
            )

        if "[[" in explanation or "]]" in explanation:
            return FinalReview(
                status=FinalStatus.UNVERIFIED,
                accepted=False,
                reason="Abstention must not invent citations",
            )

        return FinalReview(
            status=FinalStatus.ABSTAINED,
            accepted=True,
            reason="Explicit abstention accepted",
        )

    # Strict Week 2 contract:
    # Every nonempty line must be a cited claim.
    if any(
        not line.startswith("- ")
        for line in lines
    ):
        return FinalReview(
            status=FinalStatus.UNVERIFIED,
            accepted=False,
            reason="Expected cited bullet claims",
        )

    if any(
        not line[2:].split("[[", 1)[0].strip()
        for line in lines
    ):
        return FinalReview(
            status=FinalStatus.UNVERIFIED,
            accepted=False,
            reason="Empty claim text",
        )

    provenance = ledger.check_answer(
        "\n".join(lines)
    )

    if not provenance["provenance_ok"]:
        return FinalReview(
            status=FinalStatus.UNVERIFIED,
            accepted=False,
            reason="Citation provenance failed",
        )

    return FinalReview(
        status=FinalStatus.CITED,
        accepted=True,
        reason="Citation provenance accepted",
    )
