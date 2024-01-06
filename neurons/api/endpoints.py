from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/miner")
async def read_miner(coldkey: str = Query(None, description="Asymmetric encryption key, wallet id ")):
    # Replace with your actual logic using coldkey
    return {"miner_status": "active", "coldkey": coldkey}

@app.get("/validator")
async def read_validator(coldkey: str = Query(None, description="Asymmetric encryption key, wallet id")):
    # Replace with your actual logic using coldkey
    return {"validator_status": "active", "coldkey": coldkey}