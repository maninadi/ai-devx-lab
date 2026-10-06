import unittest

class EmailTests(unittest.TestCase):
    def test_format_subject(self):
        self.assertEqual(format_subject("Alice"), "Welcome Alice")
