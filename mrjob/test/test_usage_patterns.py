import datetime, json, unittest
from mrjob.segments import usage_patterns as UP

# XXX clean and move locally for checkin
TEST_DATA = '/Users/spenrose/churn/sample/testdata/fhr_8.json'

class TestFHRUsage(unittest.TestCase):

    def setUp(self):
        with open(TEST_DATA) as f:
            self.fhr = json.load(f)

    def test_simple_properties(self):
        usage = UP.FHRUsage(self.fhr)
        self.assertEqual(set(usage.data.keys()),
                         set([u'last', u'days']))
        self.assertEqual(usage.creation_date, datetime.date(2014, 6, 4))
        self.assertEqual(usage.ping_date, datetime.date(2015, 1, 28))
        self.assertEqual(usage.start_date, datetime.date(2014, 8, 1))
        self.assertEqual(usage.window, 180)
        self.assertEqual(usage.days.keys(), [u'2015-01-28'])
        self.assertEqual(usage.active_days, [])
        self.assertEqual(usage.default, {})
        self.assertEqual(usage.weekly_active_days, [0] * 25)
        activity_by_day = {'by_day': [],
                           'average_hours_per_day': '0.0',
                           'average_sessions_per_day': '0',
                           'years': '0'}
        self.assertEqual(usage.activity_by_day, activity_by_day)


if __name__ == '__main__':
    unittest.main()
