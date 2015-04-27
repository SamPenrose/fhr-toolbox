import datetime, json, unittest
from fhrpy.segments import usage_patterns as UP

# XXX clean and move locally for checkin
TEST_DATA = '/Users/spenrose/churn/sample/testdata/fhr_18.json'

class TestFHRUsage(unittest.TestCase):

    def setUp(self):
        with open(TEST_DATA) as f:
            self.fhr = json.load(f)

    def test_simple_properties(self):
        usage = UP.FHRUsage(self.fhr)
        self.assertEqual(set(usage.data.keys()),
                         set([u'last', u'days']))
        # self.assertEqual(usage.creation_date, datetime.date(2014, 6, 4))
        self.assertEqual(usage.creation_date, datetime.date(2014, 7, 2))
        # self.assertEqual(usage.ping_date, datetime.date(2015, 1, 28))
        self.assertEqual(usage.ping_date, datetime.date(2015, 4, 12))
        # self.assertEqual(usage.start_date, datetime.date(2014, 8, 1))
        self.assertEqual(usage.start_date, datetime.date(2014, 10, 14))
        self.assertEqual(usage.window, 180)
        # self.assertEqual(usage.days.keys(), [u'2015-01-28'])
        days = usage.days.keys()
        self.assertEqual(len(days), 174)
        self.assertEqual(len(usage.active_days), 174)

        default = {'active': 174.0,
                   'always': False,
                   'default': 0.0,
                   'label': 'rarely',
                   'never': True,
                   'switch_count': 0,
                   'switches': 'one',
                   'unmeasured': False}
        self.assertEqual(usage.default, default)
        self.assertEqual(usage.weekly_active_days, [0] * 25)

        average_hours_per_day = '1.7230715198'
        self.assertEqual(usage.activity_by_day['average_hours_per_day'],
                         average_hours_per_day)
        day0 = {'total_seconds': 238799, 'active_seconds': 33750,
                'day': u'2015-03-14', 'session_count': 2}
        self.assertEqual(usage.activity_by_day['by_day'][0], day0)


if __name__ == '__main__':
    unittest.main()
