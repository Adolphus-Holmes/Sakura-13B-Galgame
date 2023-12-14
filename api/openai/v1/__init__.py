import asyncio
from typing import *
from fastapi import Depends, Request
from pprint import pprint, pformat
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi import APIRouter
from transformers import GenerationConfig
from api.legacy.type import OpenAIChatCompletionRequest, OpenAIChatCompletionResponse

from sse_starlette.sse import EventSourceResponse

from utils import state

import logging
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/v1/chat",
)

async def get_output(data: OpenAIChatCompletionRequest) -> OpenAIChatCompletionResponse:
    logger.debug(f"Incoming request: \n{data.model_dump()}")
    generation_config = GenerationConfig(**data.model_dump())

    logger.info(f"translate: {data.prompt}")
    output = await state.get_model().completion_async(data.prompt, generation_config)
    # FIXME(kuriko): only for testing, remember to comment this out.
    # await asyncio.sleep(600)

    logger.info(f"answer: {output}")
    return OpenAIChatCompletionResponse(
        results=[
            OpenAIChatCompletionResponse.Result(
                new_token=output.new_token,
                text=output.text,
            )
        ]
    )


@router.post("/completions")
async def completions(req: Request, data: OpenAIChatCompletionRequest):
    ret = await get_output(data)
    json_compatible_item_data = jsonable_encoder(ret)
    return JSONResponse(content=json_compatible_item_data)


@router.post("/stream/completions")
async def completions(req: Request, data: OpenAIChatCompletionRequest):
    async def generator():
        try:
            ret: OpenAIChatCompletionResponse = await get_output(data)
            yield dict(data=ret.model_dump_json())
        except asyncio.CancelledError as e:
            logger.warning(f"Disconnected from client (via refresh/close) {req.client})")
            raise e

    return EventSourceResponse(
        generator(),
        ping=15,
        media_type = "text/event-stream",
    )
