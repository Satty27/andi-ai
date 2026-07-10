# **ANDI**: Advanced Natural Language Database Interface 🤖🍃

ANDI (Advanced Natural Language Database Interface) is an agentic Python library that transforms your MongoDB database into a natural language interface. By leveraging the reasoning capabilities of gpt-4o-mini, ANDI allows you to generate and execute complex MongoDB queries—including dynamic runtime variables—using plain English.

Instead of writing rigid CRUD endpoints, consolidate your data fetching into a single, intelligent NLP endpoint.


## ✨ Features

* 🗣️ Natural Language to NoSQL: Write your database queries in plain English. ANDI translates your intent into precise MongoDB syntax.
* 🧠 Agentic Solution: Powered by gpt-4o-mini, ANDI understands context and constructs highly accurate database operations.
* 🔒 Privacy-First Schema Management: ANDI connects via your MongoDB URI, infers the collection schema, and caches it locally. Only the schema structure is shared with the LLM—your actual database records are never exposed to the agent.
* ⚡ Runtime Variables: Safely inject dynamic variables into your natural language prompts at runtime without string-concatenation vulnerabilities.
* 🛠️ Advanced Operations: Currently supports standard find queries and complex aggregate pipelines out of the box.
* 🎯 Single Endpoint Architecture: Replace dozens of rigid REST API routes with a single, flexible natural language data-fetching endpoint.

## 📦 Installation
Available on PyPI. Install ANDI using pip: 

pip install andi-ai

## ⚙️ Prerequisites
To use ANDI, you will need:
1. A valid MongoDB Connection String URL.
2. An OpenAI API Key (with access to the gpt-4o-mini model).

## 🚀 Quick Start
Here is a basic example of how to initialize ANDI and run a natural language query against your database.
Refers test directory

`class TestProject:

    def testing_nlp(self):
        url = Connection.get_connection()
        print(url)
        status = Andi.initialize_connection(self, url=url, database_name="aristotle")
        print(status)

        user_coll = Andi.analyze_schemas(self,base_collections=["users", "wallets", "weekly_leaderboard"])
        print(user_coll)

        # Example 1
        # Please stick with database terminalogy. Strictly use field name as per schema and collection name to avoid LLM hallucination.
        # As databases are case sensistive treat NLP tool the same. Explicitly ask Regex operation.
        #
        # Basic rules to use runtime_inputs
        # "email":"${email}"
        # Left side of assignment operator must be a field name matching with schema field name
        # Right side of assignment operator "${email}" must match variable_name
        # Always provide datatype otherwise range operators like "$in" will not work if query uses one. 

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
        output = Andi.run_nlp_query(self, intent, query_identifier=None, retry=False, email=email)
        print(output)

        # Example 2
        # 
        intent = {
          "intent": {
            "goal": """
            Write an aggregate where option_selected is equal to correct_answer and create leaderboard for top 10 emails based on timesaved.
            Also perform a lookup to get the name where email matches in engagement collection from users collection""",
            "runtime_inputs":[
            ],
            "projection":["name", "email", "rank", "timesaved"]
          }
        }
        output = Andi.run_nlp_query(self, intent, query_identifier=None, retry=False)
        print(output)

        # Example 3: Query Debugging and execution

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
`

## 🏗️ How It Works
1. Schema Extraction & Caching: When you connect ANDI to your MongoDB instance, it scans the specified collections to map out the document structures, data types, and nested fields. This schema is saved locally (e.g., in a .andi_schema.json file).
2. Prompt Construction: When a query is initiated, ANDI feeds your natural language prompt, the mapped variables, and the locally cached schema to gpt-4o-mini.
3. Agentic Translation: The LLM generates the exact MongoDB find dictionary or aggregate pipeline required to satisfy the request.
4. Execution: ANDI securely executes the generated query against your MongoDB database and returns the raw Python dictionaries.

## 📖 Supported Operations
ANDI's LLM routing engine currently supports the generation and execution of:
* find(): For standard filtering, sorting, and projection operations.
* aggregate(): For complex data transformations, grouping, unwinding, and multi-stage pipelines.

(Note: Write operations like insert, update, and delete are intentionally restricted in this version to ensure read-only safety for data-fetching endpoints).

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page if you want to contribute.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.