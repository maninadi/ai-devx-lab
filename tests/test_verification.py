from agent.verification import (
    CheckResult,
    CheckStatus,
    CompletionStatus,
    evaluate_completion,
)


def make_result(
    scope: str,
    status: CheckStatus,
) -> CheckResult:
    return CheckResult(
        scope=scope,
        status=status,
        exit_code=0 if status == CheckStatus.PASS else 1,
        output="",
    )


def test_all_checks_pass():
    pricing = make_result("pricing", CheckStatus.PASS)
    suite = make_result("suite", CheckStatus.PASS)

    assert (
        evaluate_completion(pricing, suite)
        == CompletionStatus.VERIFIED
    )


def test_pricing_passes_but_suite_fails():
    pricing = make_result("pricing", CheckStatus.PASS)
    suite = make_result("suite", CheckStatus.FAIL)

    assert (
        evaluate_completion(pricing, suite)
        == CompletionStatus.SCOPED_VERIFIED
    )


def test_pricing_failure_prevents_completion():
    pricing = make_result("pricing", CheckStatus.FAIL)
    suite = make_result("suite", CheckStatus.PASS)

    assert (
        evaluate_completion(pricing, suite)
        == CompletionStatus.NOT_VERIFIED
    )