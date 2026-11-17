
from __future__ import annotations

from copy import deepcopy


REPOSITORY_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": ["answered", "abstained"],
        },
        "answer": {
            "type": "string",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": [
                    "path",
                    "start_line",
                    "end_line",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "state",
        "answer",
        "citations",
    ],
    "additionalProperties": False,
}


def with_repository_answer_format(
    request: dict,
) -> dict:
    if "text" in request:
        raise ValueError(
            "Request already defines text formatting"
        )

    return {
        **request,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "repository_answer_v1",
                "strict": True,
                "schema": deepcopy(
                    REPOSITORY_ANSWER_SCHEMA
                ),
            }
        },
    }
