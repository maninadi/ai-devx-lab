
import json
import os
from dataclasses import asdict

from openai import OpenAI

from agent.model_protocol import inspect_response


def main():
    client = OpenAI(
        timeout=20.0,
        max_retries=0,
    )

    response = client.responses.create(
        model=os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        ),
        instructions=(
            "You are testing an API response contract. "
            "Reply with exactly READY."
        ),
        input="Return the requested response.",
        max_output_tokens=128,
        store=False,
    )

    reply = inspect_response(response)

    print(
        json.dumps(
            {
                "response_id": reply.response_id,
                "model": reply.model,
                "status": reply.status,
                "text": reply.text,
                "output_types": reply.output_types,
                "requires_tools": reply.requires_tools,
                "usage": (
                    asdict(reply.usage)
                    if reply.usage is not None
                    else None
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()  # resp_0f40267ff885943a016ae92fbb594887d2bb3b51b189cae366
