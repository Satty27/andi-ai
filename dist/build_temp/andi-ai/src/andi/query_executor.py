from pymongo import errors
import re


def resolve_placeholders(target, **kwargs):
    """
    Recursively scans a dictionary or list, replacing placeholders like ${key}
    with actual values from kwargs.
    """
    if isinstance(target, str):
        match = re.search(r'\${(.*?)}', target)
        if match:
            var_name = match.group(1)
            return kwargs.get(var_name, target)
        return target

    elif isinstance(target, dict):
        return {k: resolve_placeholders(v, **kwargs) for k, v in target.items()}

    elif isinstance(target, list):
        return [resolve_placeholders(item, **kwargs) for item in target]

    return target



class ExecuteQuery:
    @classmethod
    def execute_query(cls, db_session, nlp_query, **kwargs):
        try:
            print("####### EXECUTING QUERY #######")
            operation = nlp_query.get("operation")
            collection = nlp_query.get("collection")


            if operation == "updateOne" or operation == "updateMany":
                query = nlp_query.get("query")
                update_query = nlp_query.get("update")

                query = resolve_placeholders(query, **kwargs)
                update_query = resolve_placeholders(update_query, **kwargs)


                try:
                    coll = db_session.get_collection(collection)
                    result = coll.update_one(query, update_query)
                    if result.acknowledged:
                        if result.matched_count == 0:
                            ret_json = {
                                "operation": operation,
                                "collection": collection,
                                'status': 'success',
                                "message": "no documents found: matched_count = 0",
                            }
                            return ret_json

                        ret_json = {
                            "operation": operation,
                            "collection": collection,
                            'status': 'success',
                            "message": "modified records: " + result.modified_records,
                        }
                        return ret_json

                except errors.DuplicateKeyError as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Duplicate key error: " + str(err),
                    }
                    return ret_json
                except errors.ConnectionFailure as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Failed to establish a connection:  " + str(err),
                    }
                    return ret_json
                except errors.PyMongoError as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Pymongo error:  " + str(err),
                    }
                    return ret_json

            if operation == "find":
                try:
                    query = nlp_query.get("query")
                    print("---unresolved query args---")
                    print(query)
                    print("---resolved query args---")
                    query = resolve_placeholders(query, **kwargs)
                    print(query)

                    projection = nlp_query.get("projection")
                    coll = db_session.get_collection(collection)
                    documents = coll.find(query, projection)
                    return list(documents)

                except errors.OperationFailure as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Failed to perform the operation:  " + str(err),
                    }
                    return ret_json
                except errors.ConnectionFailure as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Failed to establish a connection:  " + str(err),
                    }
                    return ret_json
                except errors.PyMongoError as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Pymongo error:  " + str(err),
                    }
                    return ret_json

            if operation == "aggregate":
                try:
                    pipeline = nlp_query.get("pipeline")
                    pipeline = resolve_placeholders(pipeline, **kwargs)

                    coll = db_session.get_collection(collection)
                    documents = coll.aggregate(pipeline)
                    return list(documents)

                except errors.OperationFailure as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Failed to perform the operation:  " + str(err),
                    }
                    return ret_json
                except errors.ConnectionFailure as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Failed to establish a connection:  " + str(err),
                    }
                    return ret_json
                except errors.PyMongoError as err:
                    ret_json = {
                        "operation": operation,
                        "collection": collection,
                        'status': 'error',
                        "message": "Pymongo error:  " + str(err),
                    }
                    return ret_json

        except Exception as e:
            print("failed to execute nlp query " + str(e))
            return None