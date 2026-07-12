import logging
from pymongo import errors


class Connection:
    @classmethod
    def get_connection(cls):
        try:
            connection_string = "mongodb://localhost:27017"
            return connection_string

        except errors.PyMongoError as e:
            logging.critical(e)
            return None
