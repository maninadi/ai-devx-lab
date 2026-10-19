from __future__ import annotations

import json

from dataclasses import dataclass
from time import sleep
from typing import Any, Callable, Literal


Decision = Literal[
    "continue",
    "replan",
    "stop",
]


@dataclass(frozen=True)
class ToolOutcome:
    result: dict[str, Any]
    decision: Decision
    attempts: int
    events: tuple[dict[str, Any], ...]


def _failure(
    code: str,
    decision: Decision,
    attempts: int,
    events: list[dict[str, Any]],
) -> ToolOutcome:

    return ToolOutcome(
        result={
            "ok": False,
            "error": {
                "code": code,
                "message": (
                    "Tool execution did not produce "
                    "usable evidence."
                ),
            },
            "recovery": decision,
        },
        decision=decision,
        attempts=attempts,
        events=tuple(events),
    )


def run_tool_safely(
    *,
    name: str,
    raw_arguments: str,
    dispatch: Callable[
        [str, dict[str, Any]],
        dict[str, Any],
    ],
    max_attempts: int = 2,
    sleep_fn: Callable[[float], None] = sleep,
) -> ToolOutcome:
    """
    Execute a read-only tool with bounded recovery.

    Automatic retries are permitted only for
    transient timeout or connection failures.

    Do not use this retry policy for tools
    with side effects.
    """

    if max_attempts not in (1, 2):
        raise ValueError(
            "max_attempts must be 1 or 2"
        )

    # Validate before dispatching anything.

    if (
        not isinstance(raw_arguments, str)
        or len(raw_arguments) > 8192
    ):
        return _failure(
            "invalid_arguments",
            "replan",
            0,
            [],
        )

    try:
        arguments = json.loads(
            raw_arguments
        )

    except (ValueError, TypeError):
        return _failure(
            "invalid_arguments",
            "replan",
            0,
            [],
        )

    if not isinstance(arguments, dict):
        return _failure(
            "invalid_arguments",
            "replan",
            0,
            [],
        )

    events: list[dict[str, Any]] = []

    for attempt in range(
        1,
        max_attempts + 1,
    ):

        events.append({
            "event": "tool_attempted",
            "attempt": attempt,
        })

        try:
            result = dispatch(
                name,
                arguments,
            )

        except (TimeoutError, ConnectionError):

            if attempt < max_attempts:

                events.append({
                    "event": "tool_retry_scheduled",
                    "attempt": attempt,
                    "error_code": "transient_error",
                })

                sleep_fn(0.1 * attempt)
                continue

            return _failure(
                "transient_exhausted",
                "replan",
                attempt,
                events,
            )

        except FileNotFoundError:

            return _failure(
                "not_found",
                "replan",
                attempt,
                events,
            )

        except PermissionError:

            return _failure(
                "permission_denied",
                "stop",
                attempt,
                events,
            )

        except ValueError:

            return _failure(
                "invalid_arguments",
                "replan",
                attempt,
                events,
            )

        except Exception:

            # Fail closed on unexpected exceptions.
            # Do not expose raw exception messages
            # or tracebacks to the model.

            return _failure(
                "internal_tool_error",
                "stop",
                attempt,
                events,
            )

        # Validate the result contract.

        if (
            not isinstance(result, dict)
            or type(result.get("ok")) is not bool
        ):
            return _failure(
                "invalid_tool_result",
                "stop",
                attempt,
                events,
            )

        if result["ok"] is False:

            # A tool-reported failure is not
            # automatically considered transient.

            return ToolOutcome(
                result=result,
                decision="replan",
                attempts=attempt,
                events=tuple(events),
            )

        return ToolOutcome(
            result=result,
            decision="continue",
            attempts=attempt,
            events=tuple(events),
        )

    raise AssertionError("Unreachable")
