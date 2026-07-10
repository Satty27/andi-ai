import logging
from pymongo import errors


class Connection:
    @classmethod
    def get_connection(cls):
        try:
            db_url = "database_url"
            return db_url

        except errors.PyMongoError as e:
            logging.critical(e)
