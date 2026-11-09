
from pathlib import Path
from types import SimpleNamespace as NS

from agent.deadline_gateway import (
    DeadlineAwareGateway,
    DeadlineBudget,
)
from agent.trace import RunTrace


class DemoClient:
    def with_options(self, **options):
        class Counter:
            def count(self, **kwargs):
                return NS(input_tokens=25)

        class Responses:
            input_tokens = Counter()

            def create(self, **kwargs):
                return NS(status="completed")

        return NS(responses=Responses())


trace = RunTrace(Path("traces/day36"))

gateway = DeadlineAwareGateway(
    DemoClient(),
    context_window=1000,
    safety_reserve_tokens=100,
    budget=DeadlineBudget.start(10),
    on_stage=lambda stage: trace.emit(
        "model_request_stage",
        stage=stage,
    ),
)

gateway.create({
    "model": "test-model",
    "input": "Hello",
    "max_output_tokens": 100,
})

print(trace.path)
print(trace.path.read_text())
