# **ANDI**: Advanced Natural Language Database Interface 🤖🍃 
## Build exclusively for MongoDB development
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
1. A valid MongoDB Connection String URL. (check TestProject)
2. An OpenAI API Key (with access to the gpt-4o-mini model). Configure in .env (check TestProject)

## 🚀 Quick Start
Here is a basic example of how to initialize ANDI and run a natural language query against your database.
Refers test directory

`class TestProject:

    def testing_nlp(self):
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
        query = andi_instance.build_nlp_query(intent, query_identifier=None, retry=False)
        print(query)

        query_output = andi_instance.run_query_executor(query, email=email)
        print(query_output)

if __name__ == "__main__":
    test_project = TestProject()
    test_project.testing_nlp(db_session=None, analyzed_schemas=[])
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