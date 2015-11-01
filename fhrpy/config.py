import os
from collections import OrderedDict

REDSHIFT = {
    'host': os.environ.get(
        'REDSHIFT_HOST',
        'moz-metrics-v2-v4-pairs.cfvijmj2d97c.us-west-2.redshift.amazonaws.com'),
    'dbname': os.environ.get('REDSHIFT_DBNAME', 'dev'),
    'port': os.environ.get('REDSHIFT_PORT', 5439),
    'user': os.environ.get('REDSHIFT_USER', 'masteruser'),
    'password': os.environ.get('REDSHIFT_PASSWORD', ''),
}

SEARCH_TABLE = os.environ.get(
    'REDSHIFT_SEARCH_TABLE',
    'v4_41release_searches')

SMALLINT = 'smallint'
VARCHAR32 = 'varchar(32)'
DATE = 'date'

SEARCH_SCHEMA = OrderedDict([
    ('clientid', VARCHAR32),
    ('active_date', DATE),
    ('yahoo', SMALLINT),
    ('google', SMALLINT),
    ('bing', SMALLINT),
    ('other', SMALLINT),
])
