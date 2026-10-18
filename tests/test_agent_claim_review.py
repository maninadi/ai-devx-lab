from agent.claim_review import LiteralFactIndex


def observed(
    path: str,
    content: str,
    end_line: int = 1,
):
    return {
        "ok": True,
        "path": path,
        "start_line": 1,
        "end_line": end_line,
        "content": content,
    }


def test_supported_literal():

    index = LiteralFactIndex()

    index.ingest(
        observed(
            "pricing.py",
            "1: GOLD_DISCOUNT = 0.15",
        )
    )

    result = index.review(
        "GOLD_DISCOUNT",
        "0.15",
    )

    assert result["status"] == "supported"
    assert result["evidence_total"] == 1


def test_contradicted_literal():

    index = LiteralFactIndex()

    index.ingest(
        observed(
            "pricing.py",
            "1: GOLD_DISCOUNT = 0.15",
        )
    )

    result = index.review(
        "GOLD_DISCOUNT",
        "0.90",
    )

    assert result["status"] == "contradicted"


def test_missing_evidence_requires_abstention():

    index = LiteralFactIndex()

    result = index.review(
        "GOLD_DISCOUNT",
        "0.15",
    )

    assert result["status"] == "insufficient"


def test_conflicting_observations():

    index = LiteralFactIndex()

    index.ingest(
        observed(
            "pricing.py",
            "1: GOLD_DISCOUNT = 0.15",
        )
    )

    index.ingest(
        observed(
            "legacy_pricing.py",
            "1: GOLD_DISCOUNT = 0.20",
        )
    )

    result = index.review(
        "GOLD_DISCOUNT",
        "0.15",
    )

    assert result["status"] == "conflicting"
    assert result["evidence_total"] == 2


def test_dynamic_expression_is_not_evaluated():

    index = LiteralFactIndex()

    added = index.ingest(
        observed(
            "pricing.py",
            "1: GOLD_DISCOUNT = calculate_rate()",
        )
    )

    assert added == 0

    result = index.review(
        "GOLD_DISCOUNT",
        "0.15",
    )

    assert result["status"] == "insufficient"


def test_different_constants_are_not_conflicts():

    index = LiteralFactIndex()

    index.ingest(
        observed(
            "pricing.py",
            (
                "1: GOLD_DISCOUNT = 0.15\n"
                "2: GOLD_PROMOTIONAL_DISCOUNT = 0.17"
            ),
            end_line=2,
        )
    )

    standard = index.review(
        "GOLD_DISCOUNT",
        "0.15",
    )

    promotional = index.review(
        "GOLD_PROMOTIONAL_DISCOUNT",
        "0.17",
    )

    assert standard["status"] == "supported"
    assert promotional["status"] == "supported"


def test_repeated_observation_is_deduplicated():

    index = LiteralFactIndex()

    result = observed(
        "pricing.py",
        "1: GOLD_DISCOUNT = 0.15",
    )

    index.ingest(result)
    index.ingest(result)

    assert len(index.facts) == 1
