from agent.state import (
    AgentState,
    PlanStep,
    StepStatus,
)

from agent.verification import (
    CheckResult,
    CheckStatus,
    CompletionStatus,
)

from agent.readiness import assess_completion


def check(scope, status):
    return CheckResult(
        scope=scope,
        status=status,
        exit_code=0 if status == CheckStatus.PASS else 1,
        output="",
    )


def test_verified_agent_can_complete():

    state = AgentState(
        goal="Fix pricing bug",
        steps=[
            PlanStep(
                description="Fix pricing logic",
                status=StepStatus.VERIFIED,
                evidence=["Pricing regression tests passed"],
            )
        ],
    )

    result = assess_completion(
        state,
        check("pricing", CheckStatus.PASS),
        check("suite", CheckStatus.PASS),
    )

    assert result.can_claim_complete
    assert result.verdict == CompletionStatus.VERIFIED


def test_unfinished_plan_prevents_completion():

    state = AgentState(
        goal="Fix pricing bug",
        steps=[
            PlanStep(
                description="Fix pricing logic",
                status=StepStatus.IN_PROGRESS,
            )
        ],
    )

    result = assess_completion(
        state,
        check("pricing", CheckStatus.PASS),
        check("suite", CheckStatus.PASS),
    )

    assert not result.can_claim_complete
    assert result.reasons


def test_failed_verification_prevents_completion():

    state = AgentState(
        goal="Fix pricing bug",
        steps=[
            PlanStep(
                description="Fix pricing logic",
                status=StepStatus.VERIFIED,
                evidence=["Targeted tests passed"],
            )
        ],
    )

    result = assess_completion(
        state,
        check("pricing", CheckStatus.PASS),
        check("suite", CheckStatus.FAIL),
    )

    assert not result.can_claim_complete
    assert result.verdict == CompletionStatus.SCOPED_VERIFIED