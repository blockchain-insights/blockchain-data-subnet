from fastapi import FastAPI, Query
from pymongo import MongoClient


app = FastAPI()

@app.get("/miner")
async def read_miner(coldkey: str = Query(None, description="Asymmetric encryption key, wallet id ")):
    # Replace with your actual logic using coldkey
    # MongoDB connection string
    # Update the string with your MongoDB instance details
    connection_string = "mongodb://localhost:27017"

    # Connect to the MongoDB client
    client = MongoClient(connection_string)

    # Select the database and collection
    # Replace 'your_database' and 'your_collection' with actual names
    db = client['miner']
    collection = db['metadata']

    # Query to fetch metadata based on uid and netuid
    query = {'uid': 0, 'netuid': 59}

    # Retrieve the data
    try:
        document = collection.find_one(query)
        if document:
            # Assuming 'metadata' is the field name containing the desired data
            document.pop('_id', None)
            return document
        else:
            return "No data found for the provided UID and NetUID."
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        # Close the connection
        client.close();

@app.get("/validator")
async def read_validator(coldkey: str = Query(None, description="Asymmetric encryption key, wallet id")):
    # Replace with your actual logic using coldkey
    # MongoDB connection string
    # Update the string with your MongoDB instance details
    connection_string = "mongodb://localhost:27017"

    # Connect to the MongoDB client
    client = MongoClient(connection_string)

    # Select the database and collection
    # Replace 'your_database' and 'your_collection' with actual names
    db = client['validator']
    collection = db['metadata']

    # Query to fetch metadata based on uid and netuid
    query = {'uid': 0, 'netuid': 59}

    # Retrieve the data
    try:
        document = collection.find_one(query)
        if document:
            # Assuming 'metadata' is the field name containing the desired data
            document.pop('_id', None)
            return document
        else:
            return "No data found for the provided UID and NetUID."
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        # Close the connection
        client.close();