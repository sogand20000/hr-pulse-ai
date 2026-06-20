# supabase_service.py
import os

from supabase import acreate_client
from supabase._async.client import AsyncClient

supabase: AsyncClient = None


async def init_supabase():
    global supabase

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

    if SUPABASE_URL and SUPABASE_KEY:
        if supabase is None:
            supabase = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
            print("⚡ Supabase Async Client initialized successfully!")
    else:
        print("❌ Supabase environment variables are missing!")


async def get_supabase_client() -> AsyncClient:
    global supabase
    if supabase is None:
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

        if SUPABASE_URL and SUPABASE_KEY:
            supabase = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
        else:
            raise RuntimeError("Supabase credentials missing in environment variables.")
    return supabase


async def get_chat_by_id(chat_id: int):

    try:
        client = await get_supabase_client()
        db_response = (
            await client.table("chats").select("history").eq("id", chat_id).execute()
        )

        return db_response
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None


async def update_chat_history(chat_id: int, chat_history: list):

    try:
        client = await get_supabase_client()
        print(
            f"🔄 [DB] Request to update history for chat_id: {chat_id} with {len(chat_history)} messages...",
            flush=True,
        )

        response = await (
            client.table("chats")
            .update({"history": chat_history})
            .eq("id", chat_id)
            .execute()
        )
        print(f"📊 [DB] Raw Update Response Data: {response.data}", flush=True)
        return response
    except Exception as e:
        print(f"❌ [DB] Error updating chat history: {e}", flush=True)
        return None


async def insert_new_chat_history(chat_history: list):

    try:
        client = await get_supabase_client()

        insert_response = (
            await client.table("chats").insert({"history": chat_history}).execute()
        )
        return insert_response
    except Exception as e:
        print(f"Error inserting new chat history: {e}")
        return None


async def insert_document(content: str, metadata: dict = None):

    try:
        from backend.src.services.rag_service import get_embedding

        chunks = chunk_text_smart(content, chunk_size=1000, overlap=200)
        print(f"📦 [RAG] Text split into {len(chunks)} chunks.")

        success_all = True

        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)

            if not embedding:
                print(f"❌ Failed to generate embedding for chunk #{i + 1}")
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
                print(
                    f"✅ Chunk #{i + 1}/{len(chunks)} successfully saved to Supabase! ID: {response.data[0]['id']}"
                )
            else:
                success_all = False

        return success_all

    except Exception as e:
        print(f"❌ Error inserting document to Supabase: {e}")
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


async def save_chat_message_vector(session_id: int, sender: str, message_text: str):
    print(f"✅ Vector saved successfully for role: {sender}")
    try:
        from backend.src.services.rag_service import get_embedding

        is_query = True if sender == "user" else False
        vector = get_embedding(message_text, is_query)

        if not vector:
            print("❌ Embedding generation failed, skipping database insert.")
            return
        client = await get_supabase_client()
        await (
            client.table("chat_messages_vectors")
            .insert(
                {
                    "session_id": session_id,
                    "sender": sender,
                    "message_text": message_text,
                    "embedding": vector,
                }
            )
            .execute()
        )

        print(f"✅ Successfully saved {sender} message vector for session {session_id}")

    except Exception as e:
        print(f"❌ Error in save_chat_message_vector: {e}")
