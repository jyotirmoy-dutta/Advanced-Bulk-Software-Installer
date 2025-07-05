import unittest

class TestSample(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(1 + 1, 2)

    def test_fail(self):
        self.assertNotEqual(2 * 2, 4)  # This will fail intentionally

if __name__ == "__main__":
    unittest.main() 