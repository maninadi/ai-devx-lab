import hashlib
import re

from dataclasses import dataclass


CITATION_PATTERN = re.compile(
    r"\[\["
    r"(?P<path>[^\]\n]+)"
    r":L(?P<start>\d+)"
    r"-L(?P<end>\d+)"
    r"\]\]"
)


@dataclass(frozen=True)
class Evidence:
    path: str
    start_line: int
    end_line: int
    sha256: str


class EvidenceLedger:
    """
    Tracks repository evidence actually returned
    to the model during one agent execution.
    """

    def __init__(self):
        self.records: list[Evidence] = []

    def record(
        self,
        tool_name: str,
        result: dict,
        *,
        truncated: bool,
    ) -> bool:

        # Only successful, complete line-range
        # observations qualify as evidence.
        if (
            tool_name != "read_file_range"
            or truncated
            or result.get("ok") is not True
        ):
            return False

        path = result.get("path")
        start = result.get("start_line")
        end = result.get("end_line")
        content = result.get("content")

        if not (
            isinstance(path, str)
            and type(start) is int
            and type(end) is int
            and 1 <= start <= end
            and isinstance(content, str)
        ):
            return False

        digest = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

        self.records.append(
            Evidence(
                path=path,
                start_line=start,
                end_line=end,
                sha256=digest,
            )
        )

        return True

    def covers(
        self,
        path: str,
        start: int,
        end: int,
    ) -> bool:
        """
        Determine whether a citation range was
        fully included in an observed excerpt.
        """

        return any(
            evidence.path == path
            and evidence.start_line <= start
            and end <= evidence.end_line
            and start <= end
            for evidence in self.records
        )

    def check_answer(self, answer: str) -> dict:
        """
        Check citation provenance for bullet-form
        claims in the final answer.

        Does NOT verify semantic correctness.
        """

        claims = [
            line.strip()
            for line in answer.splitlines()
            if line.lstrip().startswith("- ")
        ]

        issues = []
        passed = 0

        for number, claim in enumerate(
            claims,
            start=1,
        ):
            citations = list(
                CITATION_PATTERN.finditer(claim)
            )

            if not citations:
                issues.append(
                    f"Claim {number}: missing citation"
                )
                continue

            valid = all(
                self.covers(
                    path=match.group("path"),
                    start=int(match.group("start")),
                    end=int(match.group("end")),
                )
                for match in citations
            )

            if valid:
                passed += 1
            else:
                issues.append(
                    f"Claim {number}: "
                    "unobserved citation range"
                )

        if not claims:
            issues.append(
                "No bullet-form claim lines to check"
            )

        return {
            "provenance_ok": not issues,
            "claim_lines": len(claims),
            "claims_with_observed_citations": passed,
            "issues": issues,
        }
