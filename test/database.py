import logging
from pymongo import errors


class Connection:
    @classmethod
    def get_connection(cls):
        try:
            db_url = "mongodb://localhost:27017/"
            return db_url

        except errors.PyMongoError as e:
            logging.critical(e)
