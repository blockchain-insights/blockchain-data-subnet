from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from api.dashboard.database import get_user_collection
from api.dashboard.models import Miner
from api.dashboard.routers.auth import verify_access_token
from api.dashboard.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_miner", tags=["authenticated"])
async def add_miner(user_id: str, miner: Miner, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_collection.update_one({"_id": oid}, {"$push": {"miners": miner.dict()}})
    return {"message": "Miner added successfully"}

@router.delete("/user/{user_id}/delete_miner/{miner_hotkey}", tags=["authenticated"])
async def delete_miner(user_id: str, miner_hotkey: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    result = user_collection.update_one(
        {"_id": oid},
        {"$pull": {"miners": {"minerHotkey": miner_hotkey}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Miner hotkey not found or user not found")

    return {"message": "Miner deleted successfully"}

@router.get("/user/{user_id}/miners",  response_model=List[Miner], tags=["authenticated"])
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

@router.get("/miners", response_model=List[Miner], tags=["authenticated"])
async def get_all_miners(token: str = Depends(verify_access_token)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_miners = [miner for user in users for miner in user.get("miners", [])]
    return all_miners
