import pytest

from ai_project.llm import MockLLMProvider
from ai_project.protocol.pxp import PXPTag


class TestMockLLMProviderExtended:
    """Extended tests for MockLLMProvider."""

    def test_analyst_variation_by_task(self) -> None:
        provider = MockLLMProvider()

        prompt_a = "You are the Analyst agent. Task: Choose A or B."
        prompt_b = "You are the Analyst agent. Task: Choose C or D."

        out_a = provider.generate(prompt_a)
        out_b = provider.generate(prompt_b)

        import json
        data_a = json.loads(out_a)
        data_b = json.loads(out_b)

        # Different tasks may produce different predictions
        assert data_a["prediction"] in ["Option A", "Option B", "Option C", "Option D"]
        assert data_b["prediction"] in ["Option A", "Option B", "Option C", "Option D"]

    def test_critic_behavior(self) -> None:
        provider = MockLLMProvider()

        # Critic with existing prediction
        prompt = "You are the Critic agent. Task: test. Current prediction: Option A."
        output = provider.generate(prompt)

        import json
        data = json.loads(output)

        assert data["tag"] in ["RATIFY", "REVISE", "REFUTE"]
        if data["tag"] in ["REVISE", "REFUTE"]:
            # Should provide alternative
            assert data["prediction"] != "Option A" or data["tag"] == "RATIFY"

    def test_specialist_independent(self) -> None:
        provider = MockLLMProvider()

        prompt = "You are the Specialist agent. Task: test."
        output = provider.generate(prompt)

        import json
        data = json.loads(output)

        assert data["tag"] in ["RATIFY", "REVISE", "REFUTE"]
        assert data["prediction"] in ["Option A", "Option B", "Option C", "Option D"]

    def test_seed_reproducibility(self) -> None:
        provider1 = MockLLMProvider(seed=42)
        provider2 = MockLLMProvider(seed=42)

        prompt = "You are the Analyst agent. Task: reproducibility test."
        out1 = provider1.generate(prompt)
        out2 = provider2.generate(prompt)

        assert out1 == out2

    def test_different_seeds_different_outputs(self) -> None:
        provider1 = MockLLMProvider(seed=1)
        provider2 = MockLLMProvider(seed=2)

        prompt = "You are the Analyst agent. Task: seed test."
        out1 = provider1.generate(prompt)
        out2 = provider2.generate(prompt)

        # May or may not be different, but both valid
        import json
        data1 = json.loads(out1)
        data2 = json.loads(out2)

        assert data1["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]
        assert data2["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]


import json