from agent.evidence_ledger import (
    EvidenceLedger,
)


def sample_result():
    return {
        "ok": True,
        "path": "src/pricing.py",
        "start_line": 10,
        "end_line": 15,
        "content": (
            "10: STANDARD = 0.10\n"
            "11: GOLD = 0.15\n"
            "12: PROMO_GOLD = 0.17"
        ),
    }


def test_records_observed_evidence():

    ledger = EvidenceLedger()

    recorded = ledger.record(
        "read_file_range",
        sample_result(),
        truncated=False,
    )

    assert recorded
    assert len(ledger.records) == 1

    evidence = ledger.records[0]

    assert evidence.path == "src/pricing.py"
    assert evidence.start_line == 10
    assert evidence.end_line == 15
    assert len(evidence.sha256) == 64


def test_valid_citation_passes():

    ledger = EvidenceLedger()

    ledger.record(
        "read_file_range",
        sample_result(),
        truncated=False,
    )

    answer = (
        "- Gold discount is 15%. "
        "[[src/pricing.py:L11-L11]]"
    )

    report = ledger.check_answer(answer)

    assert report["provenance_ok"]
    assert report["claim_lines"] == 1
    assert (
        report["claims_with_observed_citations"]
        == 1
    )


def test_unobserved_range_fails():

    ledger = EvidenceLedger()

    ledger.record(
        "read_file_range",
        sample_result(),
        truncated=False,
    )

    answer = (
        "- Enterprise discount is 22%. "
        "[[src/pricing.py:L40-L45]]"
    )

    report = ledger.check_answer(answer)

    assert not report["provenance_ok"]


def test_missing_citation_fails():

    ledger = EvidenceLedger()

    report = ledger.check_answer(
        "- Gold customers receive 15%."
    )

    assert not report["provenance_ok"]


def test_truncated_observation_is_not_evidence():

    ledger = EvidenceLedger()

    recorded = ledger.record(
        "read_file_range",
        sample_result(),
        truncated=True,
    )

    assert not recorded
    assert ledger.records == []


def test_valid_provenance_does_not_prove_truth():

    ledger = EvidenceLedger()

    ledger.record(
        "read_file_range",
        sample_result(),
        truncated=False,
    )

    # This claim is false relative to the sample,
    # but its citation refers to observed lines.
    answer = (
        "- Gold customers receive 90%. "
        "[[src/pricing.py:L11-L11]]"
    )

    report = ledger.check_answer(answer)

    assert report["provenance_ok"]
