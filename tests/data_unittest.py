import sys
import unittest

from dice import data

class DataValidationTest(unittest.TestCase):
    def test_integer(self):
        a = data.Integer()
        self.assertFalse(a.validate('1+2'))
        self.assertFalse(a.validate('1.2'))
        self.assertTrue(a.validate('123'))
        self.assertTrue(a.validate(0))
        self.assertTrue(a.validate(sys.maxint * 2))
        self.assertTrue(a.validate(- sys.maxint * 2))

    def test_unsigned_int(self):
        a = data.UnsignedInt()
        self.assertTrue(a.validate('123'))
        self.assertFalse(a.validate('-123'))
        self.assertTrue(a.validate(0))
        self.assertTrue(a.validate(sys.maxint * 2))
        self.assertFalse(a.validate(-1))
        self.assertFalse(a.validate(-sys.maxint * 2))

    def test_positive_int(self):
        a = data.PositiveInt()
        self.assertTrue(a.validate('123'))
        self.assertFalse(a.validate('-123'))
        self.assertFalse(a.validate(0))
        self.assertTrue(a.validate(sys.maxint * 2))
        self.assertFalse(a.validate(-1))
        self.assertFalse(a.validate(-sys.maxint * 2))

    def test_short_option(self):
        a = data.ShortOption()
        self.assertFalse(a.validate('123'))
        self.assertTrue(a.validate('-123'))
        self.assertFalse(a.validate('--123'))


class DataTest(unittest.TestCase):
    def test_self_validation(self):
        for cls in data.get_datas():
            a = cls()
            for i in xrange(100):
                obj = a.generate()
                self.assertTrue(a.validate(obj))

if __name__ == '__main__':
    unittest.main()
