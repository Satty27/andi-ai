from andi import Andi
from database import Connection


class TestProject:
    def testing_nlp(self):
        url = Connection.get_connection()
        print(url)
        status = Andi.initialize_connection(self, url=url, database_name="aristotle")
        print(status)

        user_coll = Andi.analyze_schemas(self,base_collections=["users", "wallets", "weekly_leaderboard"])
        print(user_coll)

        # #Example 1
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
        # output = Andi.run_nlp_query(self, intent, query_identifier=None, retry=False, email=email)
        # print(output)
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


        # Example 3: Debug the query

        email = "test_user_8_fischertimothy@gmail.com"

        intent = {
          "intent": {
            "goal": "Find preferred_language of user where email=email",
            "runtime_inputs":[
                {
                    "email":"${email}",
                    "datatype": "string"
                }
            ],
            "projection":["name", "preferred_language"]
          }
        }
        query = Andi.build_nlp_query(self, intent, query_identifier=None, retry=False)
        print(query)

        query_output = Andi.run_query_executor(self, query, email=email)
        print(query_output)

test_project = TestProject()
test_project.testing_nlp()