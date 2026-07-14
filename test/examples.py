from andi import Andi
from database import Connection
import os

class TestProject:
    def testing_nlp(self, db_session, analyzed_schemas):
        self.db = db_session
        self.analyzed_schemas = analyzed_schemas


        connection_string = Connection.get_connection()
        print(connection_string)

        andi_instance = Andi(db_session=db_session, analyzed_schemas=analyzed_schemas)
        database_name = "aristotle"

        status = andi_instance.initialize_connection(connection_string=connection_string, database_name=database_name)

        print(status)

        user_coll = andi_instance.analyze_schemas(base_collections=["users", "wallets", "weekly_leaderboard"])
        print(user_coll)

        #Example 1

        target_email = "test_user_8_fischertimothy@gmail.com"

        intent = {
          "intent": {
            "goal": "Find the preferred_language and name of the user where email=target_email",
            "runtime_inputs":[
                {
                    "email":"${target_email}",
                    "datatype": "string"
                }
            ],
            "projection":["name", "preferred_language"]
          }
        }
        output = andi_instance.run_nlp_query(self, intent, query_identifier=None, retry=False, target_email=target_email)
        print(output)
        #
        # #Example 2
        #
        # intent = {
        #   "intent": {
        #     "goal": """
        #     Write an aggregate where option_selected is equal to correct_answer and create leaderboard for top 10 emails based on timesaved.
        #     Also perform a lookup to get the name where email matches in engagement collection from users collection""",
        #     "runtime_inputs":[
        #     ],
        #     "projection":["name", "email", "rank", "timesaved"]
        #   }
        # }
        # output = Andi.run_nlp_query(self, intent, query_identifier=None, retry=False)
        # print(output)

        #
        # # Example 3: Debug the query
        #
        # email = "test_user_8_fischertimothy@gmail.com"
        #
        # intent = {
        #   "intent": {
        #     "goal": "Find preferred_language of user where email=email",
        #     "runtime_inputs":[
        #         {
        #             "email":"${email}",
        #             "datatype": "string"
        #         }
        #     ],
        #     "projection":["name", "preferred_language"]
        #   }
        # }
        # query = andi_instance.build_nlp_query(intent, query_identifier=None, retry=False)
        # print(query)
        #
        # query_output = andi_instance.run_query_executor(query, email=email)
        # print(query_output)
        #


if __name__ == "__main__":
    test_project = TestProject()
    test_project.testing_nlp(db_session=None, analyzed_schemas=[])