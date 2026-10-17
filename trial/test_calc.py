import unittest

from calc import divide, percent


class CalcTests(unittest.TestCase):
    def test_divide(self):
        self.assertEqual(divide(7, 2), 3.5)

    def test_divide_by_zero(self):
        with self.assertRaisesRegex(ValueError, "^division by zero$"):
            divide(7, 0)

    def test_percent(self):
        self.assertEqual(percent(1, 4), 25)

    def test_percent_of_zero(self):
        with self.assertRaisesRegex(ValueError, "^division by zero$"):
            percent(1, 0)
