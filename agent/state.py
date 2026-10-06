from dataclasses import dataclass, field
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    VERIFIED = "verified"
    ABANDONED = "abandoned"


@dataclass
class PlanStep:
    description: str
    status: StepStatus = StepStatus.PENDING
    evidence: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    goal: str
    plan_version: int = 1
    steps: list[PlanStep] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)