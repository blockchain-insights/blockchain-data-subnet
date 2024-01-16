from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["dashboard"]

def get_user_collection():
    return db["users"]
def get_hotkey_collection():
    return db["hotkeys"]
