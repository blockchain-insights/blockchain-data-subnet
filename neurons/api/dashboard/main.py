from fastapi import FastAPI
from routers import user, auth, miner, validator

app = FastAPI()

app.include_router(user.router)
app.include_router(auth.router)
app.include_router(miner.router)
app.include_router(validator.router)
