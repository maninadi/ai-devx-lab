import json

from dataclasses import dataclass


class ContextBudgetExceeded(RuntimeError):
    """Raised when the observation budget is exhausted."""


@dataclass(frozen=True)
class ContextPolicy:
    max_tool_result_chars: int = 3500
    max_total_tool_chars: int = 12000

    def __post_init__(self):
        if self.max_tool_result_chars < 256:
            raise ValueError(
                "max_tool_result_chars must be >= 256"
            )

        if self.max_total_tool_chars < 256:
            raise ValueError(
                "max_total_tool_chars must be >= 256"
            )


class ToolContextBudget:
    """
    Controls how much serialized tool output
    enters a single agent run.

    This is a character budget, not a token budget.
    """

    def __init__(
        self,
        policy: ContextPolicy | None = None,
    ):
        self.policy = policy or ContextPolicy()
        self.used_chars = 0

    def prepare(
        self,
        tool_name: str,
        result: dict,
    ) -> tuple[str, dict]:

        raw = json.dumps(
            result,
            ensure_ascii=True,
        )

        remaining = (
            self.policy.max_total_tool_chars
            - self.used_chars
        )

        limit = min(
            self.policy.max_tool_result_chars,
            remaining,
        )

        if limit < 256:
            raise ContextBudgetExceeded(
                "Tool observation budget exhausted"
            )

        truncated = len(raw) > limit

        if not truncated:
            prepared = raw

        else:
            metadata = {
                "ok": result.get("ok", False),
                "tool": tool_name,
                "truncated": True,
                "original_chars": len(raw),
                "notice": (
                    "Partial preview only. "
                    "Missing content was not examined. "
                    "Request narrower evidence or "
                    "report insufficient evidence."
                ),
            }

            # Find the largest preview that still
            # fits inside the serialized JSON budget.
            low = 0
            high = len(raw)

            while low < high:
                middle = (low + high + 1) // 2

                candidate = json.dumps({
                    **metadata,
                    "preview": raw[:middle],
                })

                if len(candidate) <= limit:
                    low = middle
                else:
                    high = middle - 1

            prepared = json.dumps({
                **metadata,
                "preview": raw[:low],
            })

            if len(prepared) > limit:
                raise ContextBudgetExceeded(
                    "Budget too small for truncation metadata"
                )

        self.used_chars += len(prepared)

        diagnostics = {
            "tool": tool_name,
            "truncated": truncated,
            "original_chars": len(raw),
            "sent_chars": len(prepared),
            "cumulative_chars": self.used_chars,
        }

        return prepared, diagnostics