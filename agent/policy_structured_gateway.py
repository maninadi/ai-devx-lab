
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.output_contract import RepositoryAnswer
from agent.output_failure_policy import (
    OutputAction,
    OutputPolicyDecision,
    decide_output_policy,
)
from agent.structured_response_gateway import (
    OutputContractError,
    OutputOutcome,
)


@dataclass(frozen=True)
class PolicyResult:
    policy: OutputPolicyDecision
    answer: RepositoryAnswer | None = None
    preflight_decision: Any = None


class PolicyStructuredGateway:
    def __init__(self, gateway: Any):
        self.gateway = gateway

    def create(self, request: dict) -> PolicyResult:
        try:
            answer, preflight = self.gateway.create(
                request
            )
        except OutputContractError as exc:
            # The provider may already have returned
            # a durable response. Do not retry here.
            return PolicyResult(
                policy=decide_output_policy(
                    outcome=exc.outcome,
                ),
            )

        policy = decide_output_policy(
            outcome=OutputOutcome.VALID,
            answer=answer,
        )

        return PolicyResult(
            policy=policy,
            answer=answer,
            preflight_decision=preflight,
        )
