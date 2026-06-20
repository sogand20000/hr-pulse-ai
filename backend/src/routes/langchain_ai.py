# langchain_ai.py
from typing import Optional

from backend.src.services.langchain_service import get_langchain_rag_stream
from backend.src.services.supabase_service import (
    get_chat_by_id,
    insert_new_chat_history,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

langchain_router = APIRouter(prefix="/api/langchain", tags=["LangChain RAG Chat"])


class LangChainChatBody(BaseModel):
    message: str = Field(..., min_length=1, description="User question or message")
    chat_id: Optional[int] = Field(
        None, description="The chat ID to continue the conversation"
    )


@langchain_router.post("/chat/stream")
async def langchain_chat_stream(body: LangChainChatBody):
    user_message = body.message
    chat_id = body.chat_id
    chat_history = []
    current_chat_id = None

    if chat_id is not None:
        db_response = await get_chat_by_id(chat_id)
        if db_response and db_response.data and len(db_response.data) > 0:
            db_response = db_response.data[0]
            chat_history = db_response.get("history", [])
            current_chat_id = chat_id
        else:
            raise HTTPException(status_code=404, detail="Chat ID not found")

    if current_chat_id is None:
        insert_response = await insert_new_chat_history(chat_history)
        if insert_response and insert_response.data:
            current_chat_id = insert_response.data[0]["id"]
        else:
            raise HTTPException(status_code=500, detail="Database insert failed")

    async def event_generator():
        print(f"chat_history in event_generator:{chat_history}")
        try:
            async for chunk in get_langchain_rag_stream(
                user_message=user_message,
                chat_id=current_chat_id,
                chat_history=chat_history,
            ):
                if chunk:
                    yield str(chunk)

        except Exception as e:
            print(f"❌ Error during LangChain RAG streaming: {e}")
            yield "data: [An error occurred during LangChain streaming]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Chat-ID": str(current_chat_id),
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
