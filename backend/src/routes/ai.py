# ai.py
from typing import Optional

from backend.src.services.supabase_service import (
    get_chat_by_id,
    insert_document,
)
from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import errors
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

ai_router = APIRouter(prefix="/api", tags=["AI  Chat"])


class ChatBody(BaseModel):
    message: str = Field(
        ..., min_length=1, description="The user message cannot be empty"
    )
    chat_id: Optional[int] = Field(
        None, description="The chat ID to continue the conversation"
    )


try:
    ai_client = genai.Client()
except Exception as e:
    print(f"⚠️ Warning: Failed to initialize Gemini Client in blueprint: {e}")
    ai_client = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(errors.APIError),
    reraise=True,
)
async def call_gemini_with_retry_content(client, history):
    return await client.aio.models.generate_content(
        model="gemini-2.5-flash", contents=history
    )


async def call_gemini_with_retry_content_stream(client, history):
    return await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash", contents=history
    )


@ai_router.get("/chat/{chat_id}/history")
async def get_chat_history(chat_id: int):
    try:
        print(f"📥 [Route] Fetching history for chat_id: {chat_id}", flush=True)

        db_response = await get_chat_by_id(chat_id)
        if not db_response or not hasattr(db_response, "data") or not db_response.data:
            print(
                f"⚠️ [Route] Chat ID {chat_id} not found or DB error occurred.",
                flush=True,
            )
            return {"status": "success", "messages": []}
        raw_history = db_response.data[0].get("history", [])

        formatted_messages = [
            {
                "sender": "user" if msg["role"] == "user" else "ai",
                "text": msg["parts"][0]
                if isinstance(msg["parts"], list)
                else msg["parts"],
            }
            for msg in raw_history
        ]

        return {"status": "success", "messages": formatted_messages}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch history: {str(e)}"
        )


class KnowledgeBody(BaseModel):
    content: str = Field(
        ..., min_length=10, description="The text content of the knowledge base"
    )
    category: Optional[str] = "General"


@ai_router.post("/knowledge/add")
async def add_knowledge(body: KnowledgeBody):
    success = await insert_document(
        content=body.content, metadata={"category": body.category}
    )
    if success:
        return {
            "status": "success",
            "message": "Knowledge successfully vectorized and stored.",
        }
    raise HTTPException(status_code=500, detail="Internal server error during storage")
