"""
Port github.com/mozilla/churn-analysis/usage-patterns-jobs.R to Python.

Rather than discarding bad records, let's mark them with the reason for
rejecting them.
"""
import datetime as DT

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
        if ping_age > 180:
            reasons.append(TOO_OLD)
            return

        ping_less_180 = ping_date - DT.timedelta(180)
        start_date = max(creation_date, ping_less_180)
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

    calculate_default_status(active_days)
    if fhr['usage']['default']['unmeasured']:
        reasons.append(DEFAULT_UNMEASURED)

    def count_weekly_active_days():
        '''
        The R version threw me; here's my effort. We measure weeks Sa->Su;
        the datetime.date() object indexes them M->Su::0->6 .
        '''
        one_day = DT.timedelta(1)
        # Truncate to the first Sunday.
        start_date = fhr['usage']['start_date']
        while start_date.weekday() != 6:
            start_date = start_date + one_day

        # Truncate to the last Saturday.
        end_date = ping_date
        while end_date.weekday() != 5:
            end_date = end_date - one_day

        weeks = []
        while start_date < end_date:
            this_week = 0
            while start_date.weekday != 5:
                date_string = start_date.iso_format() # XXX fix "string" above
                if data.get(date_string):
                    this_week += 1
                start_date = start_date + one_day
            weeks.append(this_week)
        fhr['usage']['weekly_active_days'] = weeks
    count_weekly_active_days()

    def get_activity_trend():
        '''
        XXX find Python equiv to built-in R functions for determining
        slope of activity against time and p-value of finding.
        '''
    get_activity_trend()

    '''
    ## Covariate groupings.
    activity <- totalActivity(days)
    This is from mozilla/fhr-r-rollups/activity.R .
    '''
    def extract_activity(day):
        '''
        mozilla/fhr-r-rollups/activity.R : allActivity : <anon>
        XXX Do we track per-day record corruption/inadequacy?
          returning 0 will tell us *something* went wrong
        '''
        activity = day.get('org.mozilla.appSessions.previous')
        if not activity:
            return 0

        # All these are lists of integers
        clean_seconds = activity.get('cleanTotalTime')
        if not clean_seconds: # missing or []
            return 0
        aborted_seconds = activity.get('abortedTotalTime', [])
        if len(clean_seconds) != len(aborted_seconds):
            return 0
        clean_ticks = activity.get('cleanActiveTicks', [])
        aborted_ticks = activity.get('abortedActiveTicks', [])
        if ((len(clean_seconds) + len(aborted_seconds))
        != (len(clean_ticks) + len(aborted_ticks))):
            return 0
