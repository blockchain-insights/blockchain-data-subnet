from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from infrastructure.database import get_user_collection, get_hotkey_collection
from infrastructure.models import Hotkey
from api.dashboard.routers.auth import verify_access_token
from infrastructure.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_hotkey", tags=["authenticated"])
async def add_miner(user_id: str, hotkey: Hotkey, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_collection.update_one({"_id": oid}, {"$push": {"hotkeys": hotkey.dict()}})
    return {"message": "Hotkey added successfully"}

@router.delete("/user/{user_id}/delete_hotkey/{hotkey}", tags=["authenticated"])
async def delete_hotkey(user_id: str, hotkey: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    result = user_collection.update_one(
        {"_id": oid},
        {"$pull": {"hotkeys": {"hotkey": hotkey}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Miner hotkey not found or user not found")

    return {"message": "Hotkey deleted successfully"}

from typing import List
from pymongo.collection import Collection

@router.get("/user/{user_id}/hotkeys/{hotkey_type}", response_model=List[Hotkey], tags=["authenticated"])
async def get_hotkeys_for_user(user_id: str, hotkey_type: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user_collection: Collection = get_user_collection()
    hotkeys_collection: Collection = get_hotkey_collection()

    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's hotkeys of the specified type
    user_hotkeys = [hotkey['hotkey'] for hotkey in user.get("hotkeys", []) if hotkey['hotkeyType'] == hotkey_type]

    # Fetch corresponding hotkeys from the hotkeys collection
    matched_hotkeys = list(hotkeys_collection.find({"hotkey": {"$in": user_hotkeys}}))

    return matched_hotkeys


from typing import List
from pymongo.collection import Collection

@router.get("/hotkeys/{hotkey_type}", response_model=List[Hotkey], tags=["authenticated"])
async def get_all_hotkeys_of_type(hotkey_type: str, token: str = Depends(verify_access_token)):
    user_collection: Collection = get_user_collection()
    hotkeys_collection: Collection = get_hotkey_collection()

    users = user_collection.find({})

    # Filter user hotkeys based on hotkey_type
    user_hotkeys = [hotkey['hotkey'] for user in users for hotkey in user.get("hotkeys", []) if hotkey['hotkeyType'] == hotkey_type]

    # Fetch corresponding hotkeys from the hotkeys collection
    matched_hotkeys = list(hotkeys_collection.find({"hotkey": {"$in": user_hotkeys}}))

    return matched_hotkeys


from typing import List
from pymongo.collection import Collection

@router.get("/hotkeys", response_model=List[Hotkey], tags=["authenticated"])
async def get_all_hotkeys(token: str = Depends(verify_access_token)):
    user_collection: Collection = get_user_collection()
    hotkeys_collection: Collection = get_hotkey_collection()

    users = user_collection.find({})

    # Collect all hotkeys from user documents
    user_hotkeys = [hotkey['hotkey'] for user in users for hotkey in user.get("hotkeys", [])]

    # Fetch corresponding hotkeys from the hotkeys collection
    matched_hotkeys = list(hotkeys_collection.find({"hotkey": {"$in": user_hotkeys}}))

    return matched_hotkeys

