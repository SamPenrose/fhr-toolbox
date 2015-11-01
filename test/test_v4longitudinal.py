import unittest

from fhrpy import v4longitudinal as V4
from fhrpy import config

class TestAll(unittest.TestCase):

    def test_all(self):
        results = V4.get_searches('LIMIT 1')
        self.failUnless(results)
        self.failUnless(len(results[0]) == len(config.SEARCH_SCHEMA))

if __name__ == '__main__':
    unittest.main()
