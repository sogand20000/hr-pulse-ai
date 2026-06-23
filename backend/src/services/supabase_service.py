# supabase_service.py
import logging
import os
from uuid import UUID

from supabase import acreate_client
from supabase._async.client import AsyncClient

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: AsyncClient = None


async def get_supabase_client() -> AsyncClient:
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "❌ Supabase credentials missing in environment variables."
            )
        supabase = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


async def init_supabase():
    await get_supabase_client()


async def get_chat_by_id(chat_id: int):

    try:
        client = await get_supabase_client()
        db_response = (
            await client.table("chats")
            .select("history", "user_id")
            .eq("id", chat_id)
            .execute()
        )

        return db_response
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}", exc_info=True)
        return None


async def update_chat_history(chat_id: int, chat_history: list):

    try:
        client = await get_supabase_client()

        response = await (
            client.table("chats")
            .update({"history": chat_history})
            .eq("id", chat_id)
            .execute()
        )
        return response
    except Exception as e:
        logger.error(f"❌ [DB] Error updating chat history: {e}", flush=True)
        return None


async def insert_new_chat_history(chat_history: list, user_id: UUID):

    try:
        client = await get_supabase_client()

        insert_response = (
            await client.table("chats")
            .insert({"history": chat_history, "user_id": str(user_id)})
            .execute()
        )
        return insert_response
    except Exception as e:
        logger.error(f"Error inserting new chat history: {e}", exc_info=True)
        return None


async def insert_document(content: str, metadata: dict = None):

    try:
        from backend.src.services.rag_service import get_embedding

        chunks = chunk_text_smart(content, chunk_size=1000, overlap=200)

        success_all = True

        for i, chunk in enumerate(chunks):
            embedding = await get_embedding(chunk)

            if not embedding:
                logger.error(
                    f" Failed to generate embedding for chunk #{i + 1}", exc_info=True
                )
                success_all = False
                continue

            chunk_metadata = (metadata or {}).copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)

            data = {
                "content": chunk,
                "metadata": chunk_metadata,
                "embedding": embedding,
            }
            client = await get_supabase_client()
            response = await client.table("documents").insert(data).execute()

            if response.data and len(response.data) > 0:
                logger.error(
                    f"✅ Chunk #{i + 1}/{len(chunks)} successfully saved to Supabase! ID: {response.data[0]['id']}",
                    exc_info=True,
                )
            else:
                success_all = False

        return success_all

    except Exception as e:
        logger.error(f"Error inserting document to Supabase: {e}", exc_info=True)
        return False


def chunk_text_smart(text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
    chunks = []
    raw_paragraphs = text.split("\n")
    current_chunk = ""

    for para in raw_paragraphs:
        if not para.strip():
            continue
        if len(current_chunk) + len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())

            overlap_start = max(0, len(current_chunk) - overlap)
            current_chunk = current_chunk[overlap_start:] + "\n" + para
        else:
            if current_chunk:
                current_chunk += "\n" + para
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


async def save_chat_message_vector(
    chat_id: int, sender: str, message_text: str, shared_embedding: list = None
):
    try:
        from backend.src.services.rag_service import get_embedding

        is_query = True if sender == "user" else False
        if shared_embedding is None:
            shared_embedding = await get_embedding(message_text, is_query)

        if not shared_embedding:
            logger.error(
                "❌ Embedding generation failed, skipping database insert.",
                exc_info=True,
            )
            return

        client = await get_supabase_client()
        await (
            client.table("chat_messages_vectors")
            .insert(
                {
                    "chat_id": chat_id,
                    "sender": sender,
                    "message_text": message_text,
                    "embedding": shared_embedding,
                }
            )
            .execute()
        )

    except Exception as e:
        logger.error(f"Error in save_chat_message_vector: {e}", exc_info=True)
