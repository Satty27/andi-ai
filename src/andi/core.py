from .db_init import Connection
from .schema_analyzer import SchemaAnalyzer
from .premium.agents import NlPAgent
from .query_executor import ExecuteQuery
import json
import os
import logging

# Configure basic logging to capture file/OS errors without crashing unexpectedly
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')


def manage_query(query=None, query_identifier=None, retry=False):
    """
    Manages storing, updating, and fetching queries in a JSON file with robust error handling.
    """
    # 1. Input Validation
    if query is not None and not isinstance(query, str):
        raise TypeError(f"Expected 'query' to be a string or None, got {type(query).__name__}")
    if query_identifier is not None and not isinstance(query_identifier, str):
        raise TypeError(f"Expected 'query_identifier' to be a string or None, got {type(query_identifier).__name__}")
    if not isinstance(retry, bool):
        raise TypeError(f"Expected 'retry' to be a boolean, got {type(retry).__name__}")

    file_path = 'query_json.json'
    data = {}

    # 2. Safely load existing data (File I/O & Data Corruption handling)
    if os.path.exists(file_path):
        try:
            # Using utf-8 encoding prevents cross-platform reading errors
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            logging.warning(f"File {file_path} contains invalid JSON or is empty. Starting fresh. ({e})")
            data = {}
        except OSError as e:
            logging.error(f"Failed to read file {file_path} (Permission denied or locked).")
            raise RuntimeError(f"Database read error: {e}")

    # 3. Fetching logic
    if query is None:
        if not query_identifier:
            raise ValueError("You must provide a 'query_identifier' to fetch a query.")
        return data.get(query_identifier, None)

    # 4. Storing/Updating logic
    if not query_identifier:
        raise ValueError("You must provide a 'query_identifier' to store a query.")

    if query_identifier in data:
        if retry:
            data[query_identifier] = query
        else:
            ret_json = {
                "status": "success",
                "message": "Query with identifier '" + query_identifier + "' was found.",
            }
            return ret_json
    else:
        data[query_identifier] = query

    # 5. Safely write back to the file
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)
    except OSError as e:
        logging.error(f"Failed to write to file {file_path}. Check disk space and permissions.")
        raise RuntimeError(f"Database write error: {e}")
    except TypeError as e:
        # Catches edge cases where non-serializable data sneaks into the dictionary
        logging.error("Attempted to serialize invalid JSON data.")
        raise RuntimeError(f"Serialization error: {e}")

    return True


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
            nlp_query = nlp_agent.brain_agent(self.analyzed_schemas, intent)
            #manage_query(nlp_query, query_identifier, retry)
            return nlp_query
        except Exception as e:
            print("failed to run nlp query " + str(e))
            return {"result": "failed", "error": str(e) }


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
