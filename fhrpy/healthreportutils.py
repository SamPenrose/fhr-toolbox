# Copyright 2013 The Mozilla Foundation <http://www.mozilla.org/>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for querying Firefox Health Report data using jydoop."""

import datetime
from collections import namedtuple

try:
    import simplejson as json
except:
    import json

SessionInfo = namedtuple('SessionInfo', ('total', 'clean', 'active_ticks'))


SessionStartTimes = namedtuple('SessionStartTimes', ('main', 'first_pain',
    'session_restored'))


class HealthReportError(Exception):
    """Base exception for all FHR exceptions."""


class UnsupportedPayloadVersionError(HealthReportError):
    """Raised when we encounter an unsupported payload version."""


class CachedProperty(object):
    """Decorator that caches the result of a property access.

    Used as an alternative to @property.
    """

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self

        value = self.wrapped(instance)
        setattr(instance, self.wrapped.__name__, value)

        return value


class FHRPayload(object):
    """Represents a Firefox Health Report payload.

    Data can be accessed through the dict interface (just as you would the
    parsed JSON object) or through various helper properties and methods.
    """

    def __init__(self, raw):
        """Initialize from raw, unparsed JSON data."""

        self._o = json.loads(raw)
        self.raw = raw
        self.raw_size = len(raw)

        v = self._o.get('version', None)
        if v != 2:
            raise UnsupportedPayloadVersionError(v)

    def get(self, k, d):
        return self._o.get(k, d)

    def __getitem__(self, k):
        return self._o[k]

    def __contains__(self, k):
        return k in self._o

    def __iter__(self):
        return iter(self._o)

    def __len__(self):
        return len(self._o)

    @property
    def version(self):
        return self._o['version']

    @property
    def app_build_id(self):
        g = self._o.get('geckoAppInfo', {})

        return g.get('appBuildID', None)

    @property
    def platform_build_id(self):
        g = self._o.get('geckoAppInfo', {})

        return g.get('platformBuildID', None)

    @CachedProperty
    def this_ping_date(self):
        y, m, d = self._o['thisPingDate'].split('-')

        return datetime.date(int(y), int(m), int(d))

    @CachedProperty
    def last_ping_date(self):
        last = self._o.get('lastPingDate', None)

        if not last:
            return None

        y, m, d = last.split('-')

        return datetime.date(int(y), int(m), int(d))

    @property
    def channel(self):
        return self._o.get('geckoAppInfo', {}).get('updateChannel', 'unknown')

    @property
    def vendor(self):
        return self._o.get('geckoAppInfo', {}).get('vendor', None)

    def is_mozilla_build(self):
        return self.vendor == 'Mozilla'

    def is_major_channel(self):
        return self.channel in ('release', 'beta', 'aurora', 'nightly')

    @CachedProperty
    def last(self):
        return self._o.get('data', {}).get('last', {})

    @CachedProperty
    def days(self):
        """Days in this payload.

        Returns an iterable of YYYY-MM-DD formatted strings.
        """
        return sorted(self._o.get('data', {}).get('days', {}).keys())

    @property
    def system_info(self):
        return self.last.get('org.mozilla.sysinfo.sysinfo', None)

    def daily_app_info(self, reverse=False):
        return self.daily_provider_data('org.mozilla.appInfo.appinfo',
            reverse=reverse)

    @CachedProperty
    def telemetry_enabled(self):
        """Whether Telemetry is currently enabled."""
        for day, app_info in self.daily_app_info(reverse=True):
            v = app_info.get('isTelemetryEnabled', None)

            if v is not None:
                return v

        return None

    @CachedProperty
    def telemetry_ever_enabled(self):
        """Whether Telemetry was ever enabled."""
        for day, app_info in self.daily_app_info():
            if app_info.get('isTelemetryEnabled', 0) == 1:
                return True

        return False

    @CachedProperty
    def blocklist_enabled(self):
        for day, app_info in self.daily_app_info(reverse=True):
            v = app_info.get('isBlocklistEnabled', None)

            if v is not None:
                return v

        return None

    @CachedProperty
    def blocklist_ever_enabled(self):
        for day, app_info in self.daily_app_info():
            if app_info.get('isBlocklistEnabled', 0) == 1:
                return True

        return False

    @CachedProperty
    def latest_places_counts(self):
        for day, places in self.daily_provider_data('org.mozilla.places.places', reverse=True):
            try:
                return places['bookmarks'], places['pages']
            except KeyError:
                continue

        return None, None


    def errors(self):
        """Obtain all the errors in this payload as an iterable of strings.

        Ideally, payloads do not have errors.
        """
        return self._o.get('errors', [])

    def daily_data(self, reverse=False):
        """Iterate over the daily data in the payload.

        Is a generator of (day, data) tuples sorted by days, from oldest to
        newest.
        """
        data = self._o.get('data', {}).get('days', {})

        days = self.days
        if reverse:
            days.reverse()

        for day in days:
            yield day, data[day]

    def daily_provider_data(self, provider, reverse=False):
        """Obtain daily data for an individual provider.

        This is a generator of (day, data) tuples sorted by days. Sorting is
        oldest to newest unless reverse is True.
        """
        for day, data in self.daily_data(reverse=reverse):
            p = data.get(provider, None)

            if p:
                yield day, p

    def session_start_times(self):
        """Iterate over all session startup times.

        Is a generator of (day, SessionStartTimes) tuples.
        """
        for day, sessions in self.daily_provider_data('org.mozilla.appSessions.previous'):
            for i, main in enumerate(sessions.get('main', [])):
                try:
                    fp = sessions['firstPaint'][i]
                    sr = sessions['sessionRestored'][i]
                except (KeyError, IndexError):
                    continue

                yield day, SessionStartTimes(main=main, first_paint=fp,
                    session_restored=sr)

    def session_times(self):
        """Iterates over all session times.

        Is a generator of (day, SessionInfo) tuples.
        """
        for day, sessions in self.daily_provider_data('org.mozilla.appSessions.previous'):
            for i, total in enumerate(sessions.get('cleanTotalTime', [])):
                try:
                    ticks = sessions.get('cleanActiveTicks')[i]
                except (KeyError, IndexError):
                    continue

                yield day, SessionInfo(total=total, clean=True,
                    active_ticks=ticks)

            for i, total in enumerate(sessions.get('abortedTotalTime', [])):
                try:
                    ticks = sessions.get('abortedActiveTicks')[i]
                except (KeyError, IndexError):
                    continue

                yield day, SessionInfo(total=total, clean=False,
                    active_ticks=ticks)

    def daily_search_counts(self):
        for day, counts in self.daily_provider_data('org.mozilla.searches.counts'):
            if counts['_v'] != 2:
                continue

            for k, v in counts.iteritems():
                if k == '_v':
                    continue

                engine, where = k.rsplit('.', 1)

                yield day, engine, where, v



def last_saturday(d):
    """Return the Saturday on or before the date."""
    # .weekday in python starts on 0=Monday
    return d - datetime.timedelta(days=(d.weekday() + 2) % 7)


def get_six_month_window(start_string, day_dict):
    active = set()
    for d in day_dict:
        try:
            when = datetime.date(*[int(s) for s in d.split('-')])
            month = (when.year, when.month)
        except Exception:
            pass
        else:
            active.add(month)
    start = datetime.date(*[int(s) for s in start_string.split('-')])
    month_window = []
    month = (start.year, start.month + 1) # immediately subtracted; 13 OK
    for i in range(0, 6):
        y, m = month[0], month[1] - 1
        if m == 0:
            m = 12
            y -= 1
        month = (y, m)
        month_window.append(month)
    month_window.reverse()
    results = []
    for month in month_window:
        present = int(month in active)
        results.append((month, present))
    return results


def get_crash_count(day_dict):
    crash_dict = day_dict.get('org.mozilla.crashes.crashes', {})
    crash_counts = [v for k, v in crash_dict.items()
                    if k.endswith('rash')] or [0]
    return sum(crash_counts)


def daydict_to_sorted_weeks(day_dict, return_unparseable=False):
    '''
    Convert the FHR 'days' value to a sorted list of sorted lists of dicts
    whose keys are date() objects and which fall in one calendar week,
    and optionally a list of unparseable date values:
        [
            [(datetime.date(), day_dict[k]), ...], ...
        ]
    where the inner lists hold days from a calendar week in order.
    Therefore passing in:
        day_dict = {'2015-04-30': {'k1': 'v1', ...}, # Thurs
                    '2015-05-01': {'k2': 'v2', ...}, # Fri
                    '2015-05-23': {'k3': 'v3', ...}, # Note gap
    would return:
        [
            [
             {datetime.date(2015, 4, 30): {'k1': 'v1', ...}},
             {datetime.date(2015, 5, 1): {'k2': 'v2', ...}},
            ],
            [
             {datetime.date(2015, 5, 23): {'k3': 'v3', ...}}
            ]
        ]
    '''
    unparseable = []
    key_list = sorted(day_dict.keys())
    weeks = []
    week = []
    saturday = None
    for k in key_list:
        try:
            day = datetime.datetime.strptime(k, "%Y-%m-%d").date()
        except Exception, e:
            unparseable.append(k)
            continue
        if saturday is None:
            saturday = last_saturday(day)
	if week and (day - saturday > datetime.timedelta(7)):
	    weeks.append(week)
	    week = []
            saturday = last_saturday(day)
	week.append({day: day_dict[k]})
    if week:
        weeks.append(week)

    if return_unparseable:
        return weeks, unparseable
    return weeks


def weekly_crashes_to_churn_mapper(job, key, payload, churn_date):
    '''
    Did we crash in the last week we ran, and did we churn?
    How many times did we crash total, and did we churn?
    What was our average number of crashes per active day
    (NOT total days in active window), and did we churn?
    '''
    if str(churn_date) == churn_date:
        churn_date = datetime.datetime.strptime(churn_date, "%Y-%m-%d").date()
    day_dict = payload.get('data', {}).get('days', {})
    try:
        weeks = daydict_to_sorted_weeks(day_dict)
    except Exception:
        yield ('error-daydict_to_sorted_weeks', 1)
        return
    if not weeks:
        return
    try:
        churned = int(churn_date > weeks[-1][-1].keys()[0])
    except Exception:
        yield ('error-extracting-churn', 1)
        return
    try:
        crashes = tuple([sum([get_crash_count(d.values()[0])
                              for d in w])
                         for w in weeks])
    except Exception:
        yield ('error-get_crash_count', 1)
        return
    try:
        last = int(bool(crashes[-1]))
    except Exception:
        yield ('error-extracting-last', 1)
        return
    yield (('last', churned), last)
    try:
        total = sum(crashes)
    except Exception:
        yield ('error-extracting-total', 1)
        return
    yield (('total', churned), total)
    try:
        average = (total*1.0) / len(day_dict)
    except Exception:
        yield ('error-extracting-average', 1)
        return
    yield (('average', churned), average)


def base_setup(job):
    job.getConfiguration().set("mapred.job.queue.name", "research")

known_sequences = {
    '1pct': '/user/sguha/fhr/samples/output/1pct',
    '5pct': '/user/sguha/fhr/samples/output/5pct',
    'nightly': '/user/sguha/fhr/samples/output/nightly',
    'aurora': '/user/sguha/fhr/samples/output/aurora',
    'beta': '/user/sguha/fhr/samples/output/beta',
}

class FHRMapper(object):
    """Decorator used to annotate a Firefox Health Report mapping function.

    When this decorator is used, the decorated function will be passed a
    FHRPayload instance as its 2nd argument instead of the raw payload data.

    In addition, the decorator can accept arguments to automatically filter out
    payloads not meeting common properties.

        only_major_channels -- If True, only payloads belonging to Mozilla's
        major release channels will be sent through. These major channels
        include {release, beta, aurora, nightly}.

        max_day_age -- If set to an integer, payloads older than this many days
        will be filtered out.
    """
    def __init__(self, only_major_channels=False, max_day_age=None):

        self.only_major_channels = only_major_channels
        self.max_day_age = max_day_age

        self.today = datetime.date.today()

    def __call__(self, func):
        def wrapper(job, key, value):
            try:
                payload = FHRPayload(value)
            except HealthReportError:
                return

            if self.only_major_channels and not payload.is_major_channel():
                return

            if self.max_day_age:
                try:
                    d = payload.this_ping_date
                except ValueError:
                    return
                age = self.today - d

                if age.days > self.max_day_age:
                    return

            for k1, v1 in func(job, key, payload):
                yield(k1, v1)

        return wrapper
