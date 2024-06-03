import os
import random
import asyncio
import json
from datetime import datetime
import traceback
import bittensor as bt
from rich.table import Table
from rich.console import Console
import yaml

import numpy as np
from protocols.chat import ChatMessageRequest, ChatMessageResponse, ChatMessageVariantRequest, ContentType
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
import time

from starlette.responses import JSONResponse
from starlette.status import HTTP_403_FORBIDDEN

import insights
from insights.api.query import TextQueryAPI
from insights.api.rate_limiter import rate_limit_middleware
from neurons.validators.utils.uids import get_top_miner_uids
from fastapi import FastAPI, Body, HTTPException
import uvicorn
from neurons import logger


class APIServer:

    failed_prompt_msg = "Please try again. Can't receive any responses from the miners or due to the poor network connection."

    def __init__(self, config, wallet, subtensor, metagraph):
        self.app = FastAPI(title="Validator API",
                           description="API for the Validator service",
                           version=insights.__version__)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.config = config
        self.device = self.config.neuron.device
        self.wallet = wallet
        self.text_query_api = TextQueryAPI(wallet=self.wallet)
        self.subtensor = subtensor
        self.metagraph = metagraph

        self.api_key_file_path = "api_key.json"
        self.api_keys = None
        self.rate_limit_config = {"requests": 1}
        if os.path.exists(self.api_key_file_path):
            with open(self.api_key_file_path, "r") as file:
                self.api_keys = json.load(file)

        self.config_file_path = "rate_limit.json"
        if os.path.exists(self.config_file_path):
            with open(self.config_file_path, "r") as file:
                config = json.load(file)
                self.rate_limit_config = config.get("rate_limit", {"requests": 1})

        if self.api_keys:
            self.app.middleware("http")(self.rate_limit_middleware_factory(self.rate_limit_config["requests"]))

        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"Request completed: {request.method} {request.url} in {duration:.4f} seconds")
            return response

        @self.app.post("/v1/api/text_query", summary="Processes chat message requests and returns a response from a randomly selected miner", tags=["v1"])
        async def get_response(request: Request, query: ChatMessageRequest = Body(..., example={
            "network": "bitcoin",
            "prompt": "Return 3 transactions outgoing from my address bc1q4s8yps9my6hun2tpd5ke5xmvgdnxcm2qspnp9r"
        })) -> ChatMessageResponse:
            if self.api_keys is not None:
                api_key_validator = self.get_api_key_validator()
                await api_key_validator(request)

            top_miner_uids = await get_top_miner_uids(metagraph=self.metagraph, wallet=wallet, top_rate=self.config.top_rate)
            logger.info(f"Top miner UIDs are {top_miner_uids}")

            selected_miner_uids = None
            if len(top_miner_uids) >= 3:
                selected_miner_uids = random.sample(top_miner_uids, 3)
            else:
                selected_miner_uids = top_miner_uids
            top_miner_axons = [metagraph.axons[uid] for uid in selected_miner_uids]

            logger.info(f"Top miner axons: {top_miner_axons}")

            if not top_miner_axons:
                raise HTTPException(status_code=503, detail=self.failed_prompt_msg)

            # get miner response
            responses, blacklist_axon_ids = await self.text_query_api(
                axons=top_miner_axons,
                network=query.network,
                text=query.prompt,
                timeout=self.config.timeout
            )

            if not responses:
                raise HTTPException(status_code=503, detail=self.failed_prompt_msg)

            blacklist_axons = np.array(top_miner_axons)[blacklist_axon_ids]
            blacklist_uids = np.where(np.isin(np.array(self.metagraph.axons), blacklist_axons))[0]
            responded_uids = np.setdiff1d(np.array(top_miner_uids), blacklist_uids)

            # Add score to miners respond to user query
            # uids = responded_uids.tolist()
            # TODO: we store the responded UIDs to progres here and that data will be take later in scoring function
            # !! Score should go to miners hotkey not its uid !! uid can change but hotkey is unique

            selected_index = responses.index(random.choice(responses))
            response_object = ChatMessageResponse(
                miner_hotkey=self.metagraph.axons[responded_uids[selected_index]].hotkey,
                response=responses[selected_index]
            )

            # return response and the hotkey of randomly selected miner
            return response_object

        @self.app.post("/v1/api/text_query/variant", summary="Processes variant chat message requests and returns a response from a specific miner", tags=["v1"])
        async def get_response_variant(request: Request, query: ChatMessageVariantRequest = Body(..., example={
            "network": "bitcoin",
            "prompt": "Return 3 transactions outgoing from my address bc1q4s8yps9my6hun2tpd5ke5xmvgdnxcm2qspnp9r",
            "miner_hotkey": "5EExDvawjGyszzxF8ygvNqkM1w5M4hA82ydBjhx4cY2ut2yr"
        })) -> ChatMessageResponse:
            if self.api_keys is not None:
                api_key_validator = self.get_api_key_validator()
                await api_key_validator(request)

            logger.info(f"Miner {query.miner_hotkey} received a variant request.")

            try:
                miner_id = metagraph.hotkeys.index(query.miner_hotkey)
            except ValueError:
                raise HTTPException(status_code=404, detail="Miner hotkey not found")

            miner_axon = [metagraph.axons[uid] for uid in [miner_id]]
            logger.info(f"Miner axon: {miner_axon}")

            responses, _ = await self.text_query_api(
                axons=miner_axon,
                network=query.network,
                text=query.prompt,
                timeout=self.config.timeout
            )

            if not responses:
                raise HTTPException(status_code=503, detail=self.failed_prompt_msg)

            # TODO: we store the responded UIDs to progres here and that data will be take later in scoring function
            # To be considered if that creates fair result, what i someone has a valdiator and will be prompting his own miner to get better score?
            # well, he wil pay for openai usage, so he will be paying for the score, so it is fair?

            logger.info(f"Variant: {responses}")
            response_object = ChatMessageResponse(
                miner_hotkey=query.miner_hotkey,
                response=responses[0]
            )

            return response_object

        @self.app.get("/", tags=["default"])
        def healthcheck():
            return {
                "status": "ok",
                "timestamp": datetime.utcnow()
            }

    def rate_limit_middleware_factory(self, max_requests):
        async def middleware(request: Request, call_next):
            return await rate_limit_middleware(request, call_next, max_requests)
        return middleware

    def get_api_key_validator(self):
        async def validator(request: Request):
            if self.api_keys is not None:
                api_key = request.headers.get("x-api-key")
                if not api_key or not any(api_key in keys for keys in self.api_keys):
                    return JSONResponse(status_code=HTTP_403_FORBIDDEN, content={"detail": "Forbidden"})
        return validator
        
    def start(self):
        # Set the default event loop policy to avoid conflicts with uvloop
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        # Start the Uvicorn server with your app
        uvicorn.run(self.app, host="0.0.0.0", port=int(self.config.api_port), loop="asyncio")
        
