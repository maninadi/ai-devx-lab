from agent.state import AgentState, StepStatus, PlanStep

import unittest

class TestAgentState(unittest.TestCase):
    def test_plan_can_after_observations(self):
        # Create an AgentState with a goal and some observations
        agent_state = AgentState(
            goal="Support enterprise discounts",
            steps=[
                PlanStep(description="hardcode enterprise discount"),
            ],
        )

        agent_state.observations.append("Enterprise discounts must come from EnterpricePricingProvider")

        agent_state.steps[0].status = StepStatus.ABANDONED
        agent_state.steps.append(
            PlanStep("Integrate EnterprisePricingProvider")
        )
        agent_state.plan_version += 1

        assert agent_state.plan_version == 2
        assert agent_state.steps[0].status == StepStatus.ABANDONED
        assert agent_state.steps[1].status == StepStatus.PENDING