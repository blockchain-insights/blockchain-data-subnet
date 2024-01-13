from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from neurons.api.dashboard.database import get_user_collection
from neurons.api.dashboard.models import User, Miner
from neurons.api.dashboard.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_miner")
async def add_miner(user_id: str, miner: Miner, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_collection.update_one({"_id": user_id}, {"$push": {"miners": miner.dict()}})
    return {"message": "Miner added successfully"}

@router.delete("/user/{user_id}/delete_miner/{miner_hotkey}")
async def delete_miner(user_id: str, miner_hotkey: str, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    result = user_collection.update_one(
        {"_id": user_id},
        {"$pull": {"miners": {"minerHotkey": miner_hotkey}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Miner hotkey not found or user not found")

    return {"message": "Miner deleted successfully"}

@router.get("/user/{user_id}/miners", response_model=List[Miner])
async def get_miners_for_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.get("miners", [])

@router.get("/miners", response_model=List[Miner])
async def get_all_miners(token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_miners = [miner for user in users for miner in user.get("miners", [])]
    return all_miners
