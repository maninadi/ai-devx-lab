
from enum import Enum


class OutcomeAction(str, Enum):
    BLOCK = "block"
    INSPECT_RESPONSE = "inspect_response"
    RECONCILE_PROVIDER = "reconcile_provider"


def decide_outcome(
    *,
    submission_intent_exists: bool,
    response_id: str | None,
) -> OutcomeAction:
    if response_id is not None:
        return OutcomeAction.INSPECT_RESPONSE

    if submission_intent_exists:
        return OutcomeAction.RECONCILE_PROVIDER

    return OutcomeAction.BLOCK
