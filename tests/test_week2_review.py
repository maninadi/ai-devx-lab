import pytest

from agent.evidence_ledger import EvidenceLedger

from agent.week2_review import (
    FinalStatus,
    review_final_answer,
    tool_choice_for_turn,
)


def make_ledger():
    ledger = EvidenceLedger()

    ledger.record(
        tool_name="read_file_range",
        result={
            "ok": True,
            "path": "pricing.py",
            "start_line": 10,
            "end_line": 12,
            "content": (
                "10: GOLD_DISCOUNT = 0.15\n"
                "11: GOLD_PROMO = 0.17\n"
                "12: PROMO_MINIMUM = 1000"
            ),
        },
        truncated=False,
    )

    return ledger


def test_valid_cited_answer():

    ledger = make_ledger()

    result = review_final_answer(
        "- GOLD_DISCOUNT is 0.15. "
        "[[pricing.py:L10-L10]]",
        ledger,
    )

    assert result.accepted
    assert result.status == FinalStatus.CITED


def test_unobserved_citation_rejected():

    ledger = make_ledger()

    result = review_final_answer(
        "- GOLD_DISCOUNT is 0.15. "
        "[[pricing.py:L50-L50]]",
        ledger,
    )

    assert not result.accepted
    assert result.status == FinalStatus.UNVERIFIED


def test_missing_citation_rejected():

    result = review_final_answer(
        "- Gold customers receive 15%.",
        make_ledger(),
    )

    assert not result.accepted


def test_abstention_is_accepted():

    result = review_final_answer(
        "ABSTAIN: The available evidence "
        "does not establish runtime behavior.",
        EvidenceLedger(),
    )

    assert result.accepted
    assert result.status == FinalStatus.ABSTAINED


def test_empty_abstention_rejected():

    result = review_final_answer(
        "ABSTAIN: Unknown",
        EvidenceLedger(),
    )

    assert not result.accepted


def test_uncited_prose_rejected():

    result = review_final_answer(
        "Gold customers receive 15%.\n"
        "- Source value is 0.15. "
        "[[pricing.py:L10-L10]]",
        make_ledger(),
    )

    assert not result.accepted


def test_false_claim_can_pass_provenance():

    result = review_final_answer(
        "- GOLD_DISCOUNT is 90%. "
        "[[pricing.py:L10-L10]]",
        make_ledger(),
    )

    # The citation is observed, but the claim is false.
    # This gate is not a semantic verifier.
    assert result.accepted


def test_turn_policy():

    assert tool_choice_for_turn(1, 12) == "required"
    assert tool_choice_for_turn(6, 12) == "auto"
    assert tool_choice_for_turn(12, 12) == "none"


def test_single_turn_disables_tools():

    assert tool_choice_for_turn(1, 1) == "none"


def test_invalid_turn_rejected():

    with pytest.raises(ValueError):
        tool_choice_for_turn(13, 12)
