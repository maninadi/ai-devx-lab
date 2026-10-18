from __future__ import annotations

import ast
import re

from dataclasses import dataclass
from enum import StrEnum


class ReviewStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class LiteralFact:
    name: str
    value: str
    value_type: str
    path: str
    line: int


class LiteralFactIndex:
    """
    Index simple Python constant assignments
    from source excerpts observed by the agent.

    This is not a general semantic verifier.
    """

    def __init__(self) -> None:
        self.facts: list[LiteralFact] = []

    def ingest(self, result: dict) -> int:
        """
        Extract facts from a complete read_file_range
        result that has already passed the evidence gate.
        """

        if result.get("ok") is not True:
            return 0

        path = result.get("path")
        content = result.get("content")
        start = result.get("start_line")
        end = result.get("end_line")

        if not (
            isinstance(path, str)
            and path.endswith(".py")
            and isinstance(content, str)
            and type(start) is int
            and type(end) is int
            and 1 <= start <= end
        ):
            return 0

        added = 0

        for numbered_line in content.splitlines():

            match = re.match(
                r"^\s*(\d+): (.*)$",
                numbered_line,
            )

            if not match:
                continue

            line_number = int(match.group(1))

            if not start <= line_number <= end:
                continue

            code = match.group(2)

            # Bound parsing input.
            if len(code) > 300:
                continue

            try:
                parsed = ast.parse(code)
            except (
                SyntaxError,
                ValueError,
                RecursionError,
            ):
                continue

            if len(parsed.body) != 1:
                continue

            stmt = parsed.body[0]

            # Only recognize:
            #
            # CONSTANT_NAME = literal
            #
            # Do not execute expressions.

            if not (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(
                    stmt.targets[0],
                    ast.Name,
                )
                and isinstance(
                    stmt.value,
                    ast.Constant,
                )
                and type(stmt.value.value)
                in (str, int, float, bool)
            ):
                continue

            name = stmt.targets[0].id

            if not re.fullmatch(
                r"[A-Z][A-Z0-9_]*",
                name,
            ):
                continue

            value = stmt.value.value

            fact = LiteralFact(
                name=name,
                value=repr(value),
                value_type=type(value).__name__,
                path=path,
                line=line_number,
            )

            if fact not in self.facts:
                self.facts.append(fact)
                added += 1

        return added

    def review(
        self,
        name: str,
        expected_literal: str,
    ) -> dict:
        """
        Review a proposed constant value against
        observed simple literal assignments.
        """

        if (
            not isinstance(name, str)
            or not re.fullmatch(
                r"[A-Z][A-Z0-9_]{0,79}",
                name,
            )
            or not isinstance(
                expected_literal,
                str,
            )
            or len(expected_literal) > 80
        ):
            return {
                "ok": False,
                "error": "Invalid review arguments",
            }

        try:
            expected = ast.literal_eval(
                expected_literal
            )
        except (
            SyntaxError,
            ValueError,
            MemoryError,
            RecursionError,
        ):
            return {
                "ok": False,
                "error": (
                    "Expected value must be a literal"
                ),
            }

        if type(expected) not in (
            str,
            int,
            float,
            bool,
        ):
            return {
                "ok": False,
                "error": (
                    "Expected value must be scalar"
                ),
            }

        relevant = [
            fact
            for fact in self.facts
            if fact.name == name
        ]

        unique_values = {
            (fact.value_type, fact.value)
            for fact in relevant
        }

        if not relevant:
            status = ReviewStatus.INSUFFICIENT

        elif len(unique_values) > 1:
            status = ReviewStatus.CONFLICTING

        elif unique_values == {
            (
                type(expected).__name__,
                repr(expected),
            )
        }:
            status = ReviewStatus.SUPPORTED

        else:
            status = ReviewStatus.CONTRADICTED

        return {
            "ok": True,
            "status": status.value,
            "name": name,
            "expected": repr(expected),
            "evidence_total": len(relevant),
            "evidence": [
                {
                    "value": fact.value,
                    "citation": (
                        f"[[{fact.path}:"
                        f"L{fact.line}-L{fact.line}]]"
                    ),
                }
                for fact in relevant[:8]
            ],
            "evidence_limited": (
                len(relevant) > 8
            ),
            "scope": (
                "Observed simple Python literal "
                "assignments only; not runtime behavior"
            ),
        }
