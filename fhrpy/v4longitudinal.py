import psycopg2
import config as C


class FriendlierDB(object):

    def __init__(self):
        self.connection = psycopg2.connect(**C.REDSHIFT)
        self.cursor = self.connection.cursor()

    def do(self, statement, commit=True):
        try:
            self.cursor.execute(statement)
        except Exception:
            self.connection.rollback() # XXX capture error from RS
            raise
        else:
            self.connection.commit()

    def select(self, query):
        self.do(query, False)
        return self.cursor.fetchall()


db = FriendlierDB()


def get_searches(where=''):
    query = "SELECT * FROM %s %s" % (C.SEARCH_TABLE, where)
    return db.select(query)
