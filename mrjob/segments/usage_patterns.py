"""
Port github.com/mozilla/churn-analysis/usage-patterns-jobs.R to Python.

Rather than discarding bad records, let's mark them with the reason for
rejecting them.
"""
import datetime as DT, numbers
from .. import healthreportutils as HRU

FHR_RETENTION_DAYS = 180
SECONDS_PER_TICK = 5

MISSING_FIELDS = 'Missing fields: '
CORRUPTED_FIELDS = 'Corrupted fields: '
TOO_OLD = "FHR from before 180 day window"
FROM_FUTURE = "FHR from after 180 day window"
CLOCK_SKEW = 'Ping date "%s" does not fall between creation date "%s" ' \
             'and current date "%s"'
INACTIVE = 'FHR activity spanned less than two weeks'
DEFAULT_UNMEASURED = 'No data for isDefaultBrowser'


def parse_date(value):
    """
    FHR dates take the form '%Y-%m-%d', but Python's wacky date.__init__
    makes strptime() more trouble than its worth.
    """
    result = None
    parts = str(value).split('-')
    if len(parts) == 3:
        try:
            parts = [int(p) for p in parts]
            result = DT.date(*parts)
        except ValueError: # NaN or e.g. month == 0
            pass
    return result


class FHRUsage(object):
    '''
    Wrapper for the JSON blob that calculates its usage data.
    XXX integrate with healthreportutils.FHRPayload()
    '''
    def __init__(self, fhr):
        self.fhr = fhr
        self.missing_fields = set()
        self.corrupted_fields = set()
        self.other_problems = set()
        # Above here should migrate
        self.reasons = []

    @HRU.CachedProperty
    def data(self):
        result = self.fhr.get('data', {})
        if not result:
            self.missing_fields.add('data')
        return result

    @HRU.CachedProperty
    def creation_date(self):
        result = None
        iso_formatted = self.data.get('last', {}).get(
            'org.mozilla.profile.age', {}).get('profileCreation')
        if iso_formatted is None:
            self.missing_fields.add('profileCreation')
        else:
            result = parse_date(iso_formatted)
            if result is None:
                self.corrupted_fields.add('profileCreation')
        return result

    @HRU.CachedProperty
    def ping_date(self):
        result = None
        iso_formatted = self.data.get('thisPingDate')
        if iso_formatted is None:
            self.missing_fields.add('thisPingDate')
        else:
            result = parse_date(iso_formatted)
            if result is None:
                self.corrupted_fields.add('thisPingDate')
        return result

    @HRU.CachedProperty
    def start_date(self):
        if not self.creation_date or not self.ping_date:
            return None

        today = DT.datetime.now().date()
        if not ((self.creation_date <= self.ping_date)
                and (self.ping_date <= today)):
            self.other_problems.add(
                CLOCK_SKEW % (self.ping_date, self.creation_date, today))
            return None

        ping_age = (today - self.ping_date).days
        if ping_age > FHR_RETENTION_DAYS:
            self.other_problems.add(TOO_OLD)
            return None
        ping_less_retention = self.ping_date - \
                              DT.timedelta(FHR_RETENTION_DAYS)
        return max(self.creation_date, ping_less_retention)

    @HRU.CachedProperty
    def window(self):
        return (self.ping_date - self.start_date).days

    @HRU.CachedProperty
    def days(self):
        '''
        A JSON-ish list.
        '''
        result = self.data.get('days', {})
        if not result:
            self.missing_fields.add('days')
        return result

    @HRU.CacheProperty
    def active_days(self):
        '''
        XXX review with dzeber
        '''
        if not self.days or not self.ping_date or not self.start_date:
            return []
        active = [parse_date(d) for d in self.days]
        active = [d for d in active if d] # XXX flag corrupted?
        active = [d for d in active if
                  ((self.start_date <= d)
                   and
                   (d <= self.ping_date))]
        active.sort()
        if not active:
            self.other_problems.add(INACTIVE)
        elif (active[-1][0] - active[0][0]).days < 14:
            self.other_problems.add(INACTIVE)
        return active

    @HRU.CachedProperty
    def default(self):
        '''
        XXX Too specific to a particular output format.
        '''
        default_days = []
        unmeasured = True
        never = True
        switch_count = 0 # -> to int
        last = None
        for date in self.active_days:
            app_info = self.days[date.isoformat()].get(
                'org.mozilla.appInfo.appinfo', {})
            is_default = app_info.get('isDefaultBrowser')
            if is_default:
                default_days.push(date)
                unmeasured = False
            elif is_default == 0:
                unmeasured = False
                if (last is not None) and (last != is_default):
                    switch_count += 1
                last = is_default

        active = float(len(self.active_days))
        default = float(len(default_days))
        always = active == default
        never = not bool(default)
        ratio = default / active
        label = 'sometimes'
        if ratio > 0.8:
            label = 'mostly'
        elif ratio < 0.2:
            label = 'rarely'
        switches = 'one' if switch_count < 2 else 'multiple'
        return {'active': active,
                'default': default,
                'always': always,
                'label': label,
                'never': never,
                'switch_count': switch_count,
                'switches': switches,
                'unmeasured': unmeasured}

    @HRU.CachedProperty
    def weekly_active_days(self):
        '''
        The R version threw me; here's my effort. We measure weeks Sa->Su;
        the datetime.date() object indexes them M->Su::0->6 .
        '''
        one_day = DT.timedelta(1)
        # Truncate to the first Sunday.
        start_date = self.start_date
        while start_date.weekday() != 6:
            start_date = start_date + one_day
        # Truncate to the last Saturday.
        end_date = self.ping_date
        while end_date.weekday() != 5:
            end_date = end_date - one_day

        weeks = []
        while start_date < end_date:
            this_week = 0
            while start_date.weekday != 5:
                if self.data.get(start_date.iso_format()):
                    this_week += 1
                start_date = start_date + one_day
            weeks.append(this_week)
        return weeks

    def activity_trend(self):
        '''
        XXX find Python equiv to built-in R functions for determining
        slope of activity against time and p-value of finding.
        '''

    @HRU.CachedProperty
    def activity_by_day(self):
        activity = [extract_activity(self.fhr, iso_format, day)
                    for (iso_format, day) in self.days.items()]
        activity = [d for d in activity if d]
        result = {}

        average_sessions_per_day = sum(
            [d['session_count'] for d in activity]
        ) / len(self.days) # intentional truncating division
        if average_sessions_per_day >= 5:
            result['average_sessions_per_day'] = "5+"
        else:
            result['average_sessions_per_day'] = str(
                average_sessions_per_day)
        hours = sum(
            [d['total_seconds'] for d in activity] # not active_seconds
        ) / 3600.0 # truncate once, in next statement
        average_hours_per_day = hours / len(self.data['days'])
        if average_hours_per_day >= 6:
            result['average_hours_per_day'] = "6+"
        else:
            result['average_hours_per_day'] = str(average_hours_per_day)
        years = (self.ping_date - self.creation_date).days / 365
        if years >= 5:
            result['years'] = "5+"
        else:
            result['years'] = str(years)
        result['by_day'] = activity
        return result

def extract_activity(fhr, iso_format, day):
    '''
    mozilla/fhr-r-rollups/activity.R : allActivity : <anon>
    XXX Do we track per-day record corruption/inadequacy?
    '''
    activity = day.get('org.mozilla.appSessions.previous')
    if not activity:
        return {}

    # All these are lists of integers
    clean_seconds = activity.get('cleanTotalTime')
    if not clean_seconds: # missing or []
        return {}
    aborted_seconds = activity.get('abortedTotalTime', [])
    if len(clean_seconds) != len(aborted_seconds):
        return {}
    clean_ticks = activity.get('cleanActiveTicks', [])
    aborted_ticks = activity.get('abortedActiveTicks', [])

    all_times = clean_seconds + aborted_seconds
    all_ticks = clean_ticks + aborted_ticks
    if len(all_times) != len(all_ticks):
        return {}
    # XXX also test for lengths of 'firstPaint' and 'main'?

    # Filter any indices which have a bad value of either type
    # XXX Here we assume that the indices of the all_ lists can be
    # mapped to each other; theoretically we might map clean_::aborted_
    RETENTION_SECONDS = FHR_RETENTION_DAYS * 24 * 3600
    RETENTION_TICKS = RETENTION_SECONDS / SECONDS_PER_TICK
    valid_times = []
    valid_ticks = []
    for i, time_value in enumerate(all_times):
        # Do we have two valid values?
        if not isinstance(time_value, numbers.Number):
            continue
        if not (0 < time_value < RETENTION_SECONDS):
            continue
        tick_value = all_ticks[i]
        if not isinstance(tick_value, numbers.Number):
            continue
        if not (0 <= tick_value < RETENTION_TICKS):
            continue
        # Are the values coherent when compared to each other?
        if (tick_value * SECONDS_PER_TICK) > time_value:
            continue
        # Heuristics pass
        valid_times.append(time_value)
        valid_ticks.append(tick_value)
    # XXX activity.R breaks len, sum, sum into a separate function
    return {'day': iso_format,
            'session_count': len(valid_times),
            'total_seconds': sum(valid_times),
            'active_seconds': sum(valid_ticks * SECONDS_PER_TICK)}


def set_usage_segment(fhr):
    fhr['usage'] = {'segment': None}
    # Rely on Python mutable data-type behavior; caveat scriptor
    reasons = fhr['usage']['reasons_not_segmented'] = []
    missing_fields = []
    corrupted_fields = []

    data = fhr.get('data')
    if not data:
        missing_fields.append('data')

    fhr['usage']['creation_date'] = data.get('last', {}).get(
        'org.mozilla.profile.age', {}).get('profileCreation')
    if not fhr['usage']['creation_date']:
        missing_fields.append('profileCreation')
    else:
        creation_date = parse_date(fhr['usage']['creation_date'])
        if creation_date is None:
            corrupted_fields.append('profileCreation')

    def set_history_window(creation_date, ping_date):
        today = DT.datetime.now().date()
        if not ((creation_date <= ping_date) and (ping_date <= today)):
            reasons.append(CLOCK_SKEW % (ping_date, creation_date, today))
            return

        ping_age = (today - ping_date).days
        if ping_age > FHR_RETENTION_DAYS:
            reasons.append(TOO_OLD)
            return

        ping_less_retention = ping_date - DT.timedelta(FHR_RETENTION_DAYS)
        start_date = max(creation_date, ping_less_retention)
        window = (ping_date - start_date).days
        fhr['usage']['start_date'] = start_date
        fhr['usage']['window'] = window

    ping_date = fhr.get('thisPingDate')
    if not ping_date:
        missing_fields.append('thisPingDate')
    elif creation_date:
        ping_date = parse_date(ping_date)
        if ping_date is None:
            corrupted_fields.append('thisPingDate')
        else:
            set_history_window(fhr, creation_date, ping_date)

    if data.get('days'):
        if ping_date:
            # XXX review with dzeber
            active_days = [(parse_date(d), d) for d in data['days']]
            active_days = [(date, string) for (date, string) in active_days
                           if date]
            active_days = [(date, string) for (date, string) in active_days
                           if ((fhr['usage']['start_date'] <= date)
                               and
                               (date <= ping_date))]
            active_days.sort()
            if not active_days:
                reasons.append(INACTIVE)
            elif (active_days[-1][0] - active_days[0][0]).days < 14:
                reasons.append(INACTIVE)
    else:
        missing_fields.append('days')

    calculate_default_status(active_days)
    if fhr['usage']['default']['unmeasured']:
        reasons.append(DEFAULT_UNMEASURED)

    count_weekly_active_days()

    '''
    rhcollect(list(
        startdate = histinfo$startdate,
        window = histinfo$window,
        isdefault = def$group,
        toggledefault = def$nswitches,
        activedates = dateseq,
        weeklyndays = weekly,
        weeklytrend = trend,
        profyears = profyears,
        dailynsess = avgnsess,
        dailyhours = avghours),
'''
def calculate_default_status(active_days):
    """
    Track how often FF is set as the default browser.
    """
    default_days = []
    unmeasured = True
    never = True
    switch_count = 0 # -> to int
    last = None
    for (date, string) in active_days:
        app_info = data['days'][string].get(
            'org.mozilla.appInfo.appinfo', {})
        is_default = app_info.get('isDefaultBrowser')
        if is_default:
            default_days.push((date, string))
            unmeasured = False
        elif is_default == 0:
            unmeasured = False
            if (last is not None) and (last != is_default):
                switch_count += 1
                last = is_default

    active = float(len(active_days))
    default = float(len(default_days))
    always = active == default
    never = not bool(default)
    ratio = default / active
    label = 'sometimes'
    if ratio > 0.8:
        label = 'mostly'
    elif ratio < 0.2:
        label = 'rarely'
        switches = 'one' if switch_count < 2 else 'multiple'
    fhr['usage']['default'] = {'active': active,
                               'default': default,
                               'always': always,
                               'label': label,
                               'never': never,
                               'switch_count': switch_count,
                               'switches': switches,
                               'unmeasured': unmeasured}
