from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess

class CompletionStatus(str, Enum):
    VERIFIED = "verified"
    SCOPED_VERIFIED = "scoped_verified"
    NOT_VERIFIED = "not_verified"

class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class CheckResult:
    scope: str
    status: CheckStatus
    exit_code: int | None
    output: str


ALLOWED_CHECKS = {
    "pricing": "tests/test_pricing.py",
    "suite": "tests",
}


def run_check(
    scope: str,
    repo_root: Path,
) -> CheckResult:

    if scope not in ALLOWED_CHECKS:
        raise ValueError(f"Unsupported check: {scope}")

    command = [
        "uv",
        "run",
        "pytest",
        "-q",
        ALLOWED_CHECKS[scope],
    ]

    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            scope=scope,
            status=CheckStatus.TIMEOUT,
            exit_code=None,
            output="Verification exceeded the timeout.",
        )

    except OSError as exc:
        return CheckResult(
            scope=scope,
            status=CheckStatus.ERROR,
            exit_code=None,
            output=str(exc),
        )

    if result.returncode == 0:
        status = CheckStatus.PASS

    elif result.returncode == 1:
        status = CheckStatus.FAIL

    else:
        status = CheckStatus.ERROR

    return CheckResult(
        scope=scope,
        status=status,
        exit_code=result.returncode,
        output=(result.stdout + result.stderr)[-2000:],
    )




def evaluate_completion(
    pricing: CheckResult,
    suite: CheckResult,
) -> CompletionStatus:

    if pricing.status != CheckStatus.PASS:
        return CompletionStatus.NOT_VERIFIED

    if suite.status == CheckStatus.PASS:
        return CompletionStatus.VERIFIED

    return CompletionStatus.SCOPED_VERIFIED