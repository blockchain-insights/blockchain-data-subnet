from typing import Union
from fastapi import FastAPI

from neurons.validators.miner_registry import MinerRegistryManager

app = FastAPI()

@app.get("/miners/{network}/{model}")
async def get_miners(network: str, model:str):
    registry = MinerRegistryManager()
    result = registry.get_miners(network, model)
    return result


@app.get("/graphs/{network}/{model}")
async def read_item(network: str, model:str, query: Union[str, None] = None):
    return {"item_id"}