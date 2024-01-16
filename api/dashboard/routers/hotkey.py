from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from infrastructure.database import get_user_collection
from infrastructure.models import Hotkey
from api.dashboard.routers.auth import verify_access_token
from infrastructure.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_hotkey/{hotkey_type}", tags=["authenticated"])
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

    return {"message": "Miner deleted successfully"}

@router.get("/user/{user_id}/hotkeys/{hotkey_type}",  response_model=List[Hotkey], tags=["authenticated"])
async def get_miners_for_user(user_id: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.get("miners", [])

@router.get("/hotkeys/{hotkey_type}", response_model=List[Hotkey], tags=["authenticated"])
async def get_all_miners(token: str = Depends(verify_access_token)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_miners = [miner for user in users for miner in user.get("miners", [])]
    return all_miners

@router.get("/hotkeys", response_model=List[Hotkey], tags=["authenticated"])
async def get_all_miners(token: str = Depends(verify_access_token)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_miners = [miner for user in users for miner in user.get("miners", [])]
    return all_miners
