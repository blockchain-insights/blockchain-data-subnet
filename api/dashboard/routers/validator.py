from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from api.dashboard.database import get_user_collection
from api.dashboard.models import Validator
from api.dashboard.routers.auth import verify_access_token
from api.dashboard.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_validator")
async def add_validator(user_id: str, validator: Validator, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_collection.update_one({"_id": oid}, {"$push": {"validators": validator.dict()}})
    return {"message": "Validator added successfully"}

@router.delete("/user/{user_id}/delete_validator/{validator_hotkey}")
async def delete_validator(user_id: str, validator_hotkey: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    result = user_collection.update_one(
        {"_id": oid},
        {"$pull": {"validators": {"validatorHotkey": validator_hotkey}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Validator hotkey not found or user not found")

    return {"message": "Validator deleted successfully"}

@router.get("/user/{user_id}/validators", response_model=List[Validator])
async def get_validators_for_user(user_id: str, token: str = Depends(verify_access_token)):
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.get("validators", [])

@router.get("/validators", response_model=List[Validator])
async def get_all_validators(token: str = Depends(verify_access_token)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_validators = [validator for user in users for validator in user.get("validators", [])]
    return all_validators
