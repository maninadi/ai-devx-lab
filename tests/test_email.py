import unittest
from src.notifications.email import format_subject

class EmailTests(unittest.TestCase):
    def test_format_subject(self):
        self.assertEqual(format_subject("Alice"), "Hello Alice")
