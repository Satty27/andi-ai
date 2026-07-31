from .db_init import Connection
from .schema_analyzer import SchemaAnalyzer
from .premium.agents import NlPAgent
from .query_executor import ExecuteQuery
import json
import os
import logging

# Configure basic logging to capture file/OS errors without crashing unexpectedly
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')


def persist_query(query=None, query_identifier=None):
    try:
        file_path = 'queries.json'
        data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
            except json.JSONDecodeError as e:
                logging.warning(f"File {file_path} contains invalid JSON or is empty. Starting fresh. ({e})")
                data = {}
            except OSError as e:
                logging.error(f"Failed to read file {file_path}.")
                raise RuntimeError(f"Database read error: {e}")

        data[query_identifier] = query
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4)
        except OSError as e:
            logging.error(f"Failed to write to file {file_path}.")
            raise RuntimeError(f"Failed to write: {e}")
        except TypeError as e:
            logging.error("Attempted to serialize invalid JSON data.")
            raise RuntimeError(f"Serialization error: {e}")

        return True
    except Exception as e:
        print("failed to save query " + str(e))
        return None


def fetch_query(query_identifier):
    try:
        file_path = 'queries.json'
        if not isinstance(query_identifier, str):
            raise TypeError(f"Expected 'query_identifier' to be a string, got {type(query_identifier).__name__}")

        if not query_identifier.strip():
            raise ValueError("The 'query_identifier' cannot be an empty string.")

        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            logging.error(f"File {file_path} contains invalid JSON. Cannot fetch data. ({e})")
            return None
        except OSError as e:
            logging.error(f"Failed to read file {file_path}.")
            raise RuntimeError(f"Database read error: {e}")

        return data.get(query_identifier, None)
    except Exception as e:
        logging.error(f"Failed to read file")


class Andi:
    def __init__(self, db_session:str, analyzed_schemas: list):
        self.db = db_session
        self.analyzed_schemas = analyzed_schemas



    def initialize_connection(self,connection_string: str, database_name:str):
        try:
            db = Connection.initialize_database(connection_string, database_name)
            #if not db.result:
            self.db = db
            print("initialized connection")
            return {"result": "success", "message":"initialized connection" }
        except Exception as e:
            # Write proper database exception if connectivity fails
            print("database connection initialization failed " + str(e))
            return {"result": "failed", "error": str(e)}

    def analyze_schemas(self, base_collections, query_identifier=None, sample_size=None):
        try:
            schema_analysis = SchemaAnalyzer.analyze_schemas(self.db, base_collections, query_identifier, sample_size)
            if not schema_analysis:
                raise Exception

            self.analyzed_schemas = schema_analysis
            print("schema analysis completed")
            return {"result": "success", "message":"schema analyzed successfully" }
        except Exception as e:
            print("failed to analyze schema " + str(e))
            return {"result": "failed", "error": str(e)}


    def build_nlp_query(self, intent, query_identifier=None, retry=False):
        try:
            nlp_agent = NlPAgent()

            if query_identifier is not None:
                nlp_query = nlp_agent.brain_agent(self.analyzed_schemas, intent)
                persist_query(nlp_query, query_identifier)
                return nlp_query

            nlp_query = nlp_agent.brain_agent(self.analyzed_schemas, intent)
            return nlp_query
        except Exception as e:
            print("failed to run nlp query " + str(e))
            return {"result": "failed", "error": str(e) }
        
        
    def fetch_query_by_identifier(self, query_identifier):
        try:
            nlp_query = fetch_query(query_identifier)
            return nlp_query
        except Exception as e:
            print("failed to fetch query by identifier " + str(e))


    def run_query_executor(self, nlp_query, **kwargs):
        try:
            query_executor = ExecuteQuery()
            query_output = query_executor.execute_query(self.db, nlp_query, **kwargs)
            return query_output
        except Exception as e:
            print("failed to run nlp query " + str(e))
            return {"result": "failed", "error": str(e) }

    def run_nlp_query(self, intent, query_identifier=None, retry=False, **kwargs):
        try:
            nlp_agent = NlPAgent()
            nlp_query = nlp_agent.brain_agent(self.analyzed_schemas, intent)

            query_executor = ExecuteQuery()
            query_output = query_executor.execute_query(self.db, nlp_query, **kwargs)
            return query_output
        except Exception as e:
            print("failed to run nlp query " + str(e))
            return {"result": "failed", "error": str(e) }
