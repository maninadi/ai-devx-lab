
from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class AnswerState(str, Enum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"


class EvidenceCitation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_line < self.start_line:
            raise ValueError(
                "end_line must be >= start_line"
            )
        return self


class RepositoryAnswer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    state: AnswerState
    answer: str
    citations: list[EvidenceCitation]

    @model_validator(mode="after")
    def validate_answer_state(self):
        if self.state == AnswerState.ANSWERED:
            if not self.answer.strip():
                raise ValueError(
                    "Answered result requires text"
                )
            if not self.citations:
                raise ValueError(
                    "Answered result requires citations"
                )
        else:
            if self.answer.strip():
                raise ValueError(
                    "Abstention must have empty answer"
                )
            if self.citations:
                raise ValueError(
                    "Abstention must have no citations"
                )

        return self
