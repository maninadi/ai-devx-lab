
import json
import os

from openai import OpenAI

from agent.model_request_gateway import (
    ModelRequestGateway,
)


def main():
    client = OpenAI()

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-4.1-mini",
    )

    # Set this only after verifying the
    # selected model's published context limit.
    context_window = int(
        os.environ["OPENAI_CONTEXT_WINDOW"]
    )

    gateway = ModelRequestGateway(
        client,
        context_window=context_window,
        safety_reserve_tokens=1024,
    )

    request = {
        "model": model,
        "instructions": (
            "Answer in one short sentence."
        ),
        "input": (
            "What is the purpose of token "
            "preflight in a coding agent?"
        ),
        "max_output_tokens": 128,
        "store": False,
    }

    response, decision = gateway.create(
        request
    )

    usage = response.usage

    print(json.dumps({
        "model": model,
        "response_status": response.status,
        "preflight_input_tokens": (
            decision.input_tokens
        ),
        "actual_input_tokens": (
            getattr(usage, "input_tokens", None)
        ),
        "actual_output_tokens": (
            getattr(usage, "output_tokens", None)
        ),
        "input_limit": decision.input_limit,
        "remaining_budget": (
            decision.remaining_tokens
        ),
        "answer": response.output_text,
    }, indent=2))


if __name__ == "__main__":
    main()
