from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["yourDatabase"]

def get_user_collection():
    return db["users"]
