import os
from andi import Andi

# 1. Initialize ANDI
andi = Andi(db_session="", analyzed_schemas=[])

# 2. Connect to your MongoDB instance
MONGO_URI =  "mongodb://localhost:27017"
DATABASE_NAME = "database_name"

andi.initialize_connection(connection_string=MONGO_URI, database_name=DATABASE_NAME)

# 3. Analyze and locally cache the schema structure for required collections
# (Your database records never leave your local environment)
andi.analyze_schemas(base_collections=["users", "wallets", "weekly_leaderboard"])

# 4. Define a natural language intent with safe runtime variables
target_email = "test_user_8_fischertimothy@gmail.com"

intent = {
    "intent": {
        "goal": "Find the preferred_language and name of the user where email=target_email",
        "runtime_inputs": [
            {
                "email": "${target_email}",
                "datatype": "string"
            }
        ],
        "projection": ["name", "preferred_language"]
    }
}

# 5. Build the optimized NLP query execution plan
query_plan = andi.build_nlp_query(intent, query_identifier=None)
print(query_plan)
# 6. Execute safely against your database. Make sure passing argument name and variable name must match to resolve during runtime.
result = andi.run_query_executor(query_plan, target_email=target_email)

print(result)
#[{'name': 'Scott Watkins', 'preferred_language': 'en'}]