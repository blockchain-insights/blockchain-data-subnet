from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from neurons.api.dashboard.database import get_user_collection
from neurons.api.dashboard.models import User, Validator
from neurons.api.dashboard.security import oauth2_scheme

router = APIRouter()

@router.post("/user/{user_id}/add_validator")
async def add_validator(user_id: str, validator: Validator, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_collection.update_one({"_id": user_id}, {"$push": {"validators": validator.dict()}})
    return {"message": "Validator added successfully"}

@router.delete("/user/{user_id}/delete_validator/{validator_hotkey}")
async def delete_validator(user_id: str, validator_hotkey: str, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    result = user_collection.update_one(
        {"_id": user_id},
        {"$pull": {"validators": {"validatorHotkey": validator_hotkey}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Validator hotkey not found or user not found")

    return {"message": "Validator deleted successfully"}

@router.get("/user/{user_id}/validators", response_model=List[Validator])
async def get_validators_for_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.get("validators", [])

@router.get("/validators", response_model=List[Validator])
async def get_all_validators(token: str = Depends(oauth2_scheme)):
    user_collection = get_user_collection()
    users = user_collection.find({})

    all_validators = [validator for user in users for validator in user.get("validators", [])]
    return all_validators
