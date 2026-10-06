import unittest
from src import calculate_discount



class PricingTests(unittest.TestCase):
    def test_standard_customer_no_discount(self):
        self.assertEqual(calculate_discount(100, "standard"), 0)
    
    def test_silver_customer_discount(self):
        self.assertEqual(calculate_discount(100, "silver"), 5)
    
    def test_gold_customer_discount(self):
        self.assertEqual(calculate_discount(100, "gold"), 15)

    def test_golf_promotion_discount(self):
        self.assertEqual(calculate_discount(1200, "gold"), 204)


if __name__ == "__main__":
    unittest.main()
