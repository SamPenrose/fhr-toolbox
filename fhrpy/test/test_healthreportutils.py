import datetime, json, unittest
from fhrpy import healthreportutils as HRU


class Test_healthreportutils(unittest.TestCase):

    def test_get_month_window(self):
        start_string = '2010-03-01'
        day_dict = {}
        window = HRU.get_five_month_window(start_string, day_dict)
        self.assertEqual(window,
                         [((2009, 11), 0), ((2009, 12), 0), ((2010, 1), 0),
                          ((2010, 2), 0), ((2010, 3), 0)])
        start_string = '2000-12-31'
        day_dict = {'2001-01-01': 1, '2000-07-31': 1} # outside window
        window = HRU.get_five_month_window(start_string, day_dict)
        self.assertEqual(window,
                         [((2000, 8), 0), ((2000, 9), 0), ((2000, 10), 0),
                          ((2000, 11), 0), ((2000, 12), 0)])

        start_string = '2010-09-27'
        day_dict = {'2010-09-01': 1, '2010-09-30': 1,
                    '2010-05-31': 1} # beginning and end with gap
        window = HRU.get_five_month_window(start_string, day_dict)
        self.assertEqual(window,
                         [((2010, 5), 1), ((2010, 6), 0), ((2010, 7), 0),
                          ((2010, 8), 0), ((2010, 9), 1)])
        day_dict = {'2010-04-01': 1, '2010-06-01': 1, # internal w/ gap
                    '2010-08-30': 1, '2099-08-30': 1} # plus outside
        window = HRU.get_five_month_window(start_string, day_dict)
        self.assertEqual(window,
                         [((2010, 5), 0), ((2010, 6), 1), ((2010, 7), 0),
                          ((2010, 8), 1), ((2010, 9), 0)])

    def test_get_crashes_in_week(self):
        KEY = 'org.mozilla.crashes.crashes'
        target_date = datetime.date(2015, 4, 26)
        dict_of_days = {}
        self.assertEqual(HRU.get_crashes_in_week(target_date, dict_of_days), 0)
        # one day on either side returns 0
        dict_of_days = {'2015-04-25': {KEY: {'crash': 5}},
                        '2015-05-03': {KEY: {'crash': 3}}}
        self.assertEqual(HRU.get_crashes_in_week(target_date, dict_of_days), 0)
        dict_of_days = {'2015-04-26': {KEY: {'crash': 5}},
                        '2015-05-01': {KEY: {'crash': 3, 'brash': 1}}}
        self.assertEqual(HRU.get_crashes_in_week(target_date, dict_of_days), 9)

    def test_daydict_to_sorted_weeks(self):
        day_dict = {'2015-04-30': {'k1': 'v1'}, # Thurs
                    '2015-05-01': {'k2': 'v2'}, # Fri
                    '2015-05-23': {'k3': 'v3'}} # Note gap
        expected = [
            [{datetime.date(2015, 4, 30): {'k1': 'v1'}},
             {datetime.date(2015, 5, 1): {'k2': 'v2'}},],
            [{datetime.date(2015, 5, 23): {'k3': 'v3'}}]
        ]

        self.assertEqual(HRU.daydict_to_sorted_weeks(day_dict), expected)
        self.assertEqual(HRU.daydict_to_sorted_weeks({}, True),
                         ([], []))
        bad = 'not an ISO formatted date'
        day_dict[bad] = {}
        self.assertEqual(HRU.daydict_to_sorted_weeks(day_dict, True),
                         (expected, [bad]))

if __name__ == '__main__':
    unittest.main()
