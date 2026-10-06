import unittest
from unittest.mock import Mock
from src import calculate_discount
from src.pricing.enterprise import EnterprisePricingProvider



class PricingTests(unittest.TestCase):
    def test_standard_customer_no_discount(self):
        self.assertEqual(calculate_discount(100, "standard"), 0)
    
    def test_silver_customer_discount(self):
        self.assertEqual(calculate_discount(100, "silver"), 5)
    
    def test_gold_customer_discount(self):
        self.assertEqual(calculate_discount(100, "gold"), 15)

    def test_golf_promotion_discount(self):
        self.assertEqual(calculate_discount(1200, "gold"), 204)

    def test_enterprise_uses_customer_specific_provider_rate(self):
        for rate, expected in ((0, 0), (0.12, 120), (0.18, 180)):
            with self.subTest(rate=rate):
                provider = Mock(spec=EnterprisePricingProvider)
                provider.get_discount_rate.return_value = rate
                self.assertEqual(calculate_discount(
                    1000, "enterprise", customer_id="customer-1",
                    enterprise_provider=provider,
                ), expected)
                provider.get_discount_rate.assert_called_once_with("customer-1")

    def test_enterprise_discount_cap(self):
        for rate in (0.20, 0.25, 1):
            with self.subTest(rate=rate):
                provider = Mock(spec=EnterprisePricingProvider)
                provider.get_discount_rate.return_value = rate
                self.assertEqual(calculate_discount(
                    1000, "enterprise", customer_id="customer-1",
                    enterprise_provider=provider,
                ), 200)

    def test_enterprise_requires_provider_and_customer(self):
        with self.assertRaises(ValueError):
            calculate_discount(1000, "enterprise", customer_id="customer-1")
        with self.assertRaises(ValueError):
            calculate_discount(1000, "enterprise", enterprise_provider=Mock())

    def test_enterprise_rejects_invalid_rate(self):
        for rate in (-0.1, 1.1, float("nan"), float("inf"), True):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                provider = Mock(spec=EnterprisePricingProvider)
                provider.get_discount_rate.return_value = rate
                calculate_discount(1000, "enterprise", customer_id="customer-1",
                                   enterprise_provider=provider)

    def test_enterprise_propagates_service_failure(self):
        provider = Mock(spec=EnterprisePricingProvider)
        provider.get_discount_rate.side_effect = RuntimeError("Service unavailable")
        with self.assertRaisesRegex(RuntimeError, "Service unavailable"):
            calculate_discount(1000, "enterprise", customer_id="customer-1",
                               enterprise_provider=provider)

    def test_existing_tiers_and_non_positive_orders_do_not_call_provider(self):
        provider = Mock(spec=EnterprisePricingProvider)
        for tier, expected in (("standard", 0), ("silver", 60), ("gold", 204)):
            self.assertEqual(calculate_discount(
                1200, tier, customer_id="customer-1", enterprise_provider=provider,
            ), expected)
        for subtotal in (0, -100):
            self.assertEqual(calculate_discount(
                subtotal, "enterprise", customer_id="customer-1", enterprise_provider=provider,
            ), 0)
        provider.get_discount_rate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
