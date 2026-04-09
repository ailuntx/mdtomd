import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mdtomd.pricing import estimate_cost, lookup_model_price


class PricingTests(TestCase):
    def test_lookup_model_price_supports_provider_fallback(self) -> None:
        price = lookup_model_price("openai-codex", "gpt-5.4-mini")

        self.assertIsNotNone(price)
        assert price is not None
        self.assertEqual(price.currency, "USD")
        self.assertEqual(price.input_per_million, 0.75)
        self.assertEqual(price.output_per_million, 4.5)

    def test_lookup_model_price_supports_model_alias(self) -> None:
        price = lookup_model_price("openrouter", "google/gemini-2.5-flash-lite")

        self.assertIsNotNone(price)
        assert price is not None
        self.assertEqual(price.currency, "USD")
        self.assertEqual(price.input_per_million, 0.1)
        self.assertEqual(price.output_per_million, 0.4)

    def test_lookup_model_price_supports_anthropic_latest_alias(self) -> None:
        price = lookup_model_price("anthropic", "claude-3-5-sonnet-latest")

        self.assertIsNotNone(price)
        assert price is not None
        self.assertEqual(price.currency, "USD")
        self.assertEqual(price.input_per_million, 3.0)
        self.assertEqual(price.output_per_million, 15.0)

    def test_lookup_model_price_supports_provider_passthrough_alias(self) -> None:
        price = lookup_model_price("ai-gateway", "openai/gpt-4.1-mini")

        self.assertIsNotNone(price)
        assert price is not None
        self.assertEqual(price.currency, "USD")
        self.assertEqual(price.input_per_million, 0.4)
        self.assertEqual(price.output_per_million, 1.6)

    def test_estimate_cost_uses_per_million_prices(self) -> None:
        price = lookup_model_price("deepseek", "deepseek-chat")
        assert price is not None

        cost = estimate_cost(price, input_tokens=154, approx_output_tokens=60)

        self.assertGreater(cost.input_cost, 0)
        self.assertGreater(cost.total_cost_if_source_tokens_match, cost.input_cost)

