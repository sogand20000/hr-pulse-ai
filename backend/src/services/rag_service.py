# rag_service.py
import os

from backend.src.services.supabase_service import get_supabase_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")

ai_client = genai.Client(api_key=api_key)


async def get_embedding(text: str, is_query: bool = False) -> list:
    task = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    try:
        response = await ai_client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=768),
        )
        if response.embeddings:
            return response.embeddings[0].values
        return None

    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        return None


async def retrieve_relevant_context(
    query: str,
    query_embedding: list = None,
    match_count: int = None,
    threshold: float = None,
) -> str:

    if match_count is None:
        env_count = os.environ.get("RAG_MATCH_COUNT")
        match_count = int(env_count) if env_count else 3

    if threshold is None:
        env_threshold = os.environ.get("RAG_MATCH_THRESHOLD")
        threshold = float(env_threshold) if env_threshold else 0.4

    try:
        if query_embedding is None:
            query_embedding = await get_embedding(query)

        if not query_embedding:
            return []

        print(
            f"⏳ [RAG] Calling match_documents in Supabase (Threshold: {threshold})..."
        )
        client = await get_supabase_client()
        db_response_documents = await client.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": match_count,
            },
        ).execute()
        print(f"📊 [RAG] Database raw response: {db_response_documents.data}")
        if db_response_documents.data and len(db_response_documents.data) > 0:
            for i, row in enumerate(db_response_documents.data):
                print(
                    f"📌 Match #{i + 1}: ID={row['id']} | Similarity={row.get('similarity')}  | Text={row['content'][:30]}..."
                )

            context_list = [row["content"] for row in db_response_documents.data]
            return "\n\n---\n\n".join(context_list)

        print("🔍 [RAG] No relevant context met the threshold in database.")
        return ""

    except Exception as e:
        print(f"❌ [RAG] Error during retrieval: {e}")
        return ""


async def retrieve_similar_past_messages(
    query: str,
    user_id: int,
    query_embedding: list = None,
    match_count: int = 3,
    threshold: float = 0.5,
) -> list:
    try:
        if query_embedding is None:
            query_embedding = await get_embedding(query)

        if not query_embedding:
            return ""

        if not query_embedding:
            return []

        client = await get_supabase_client()

        print(
            f"⏳ [Semantic Memory] Calling match_chat_messages RPC for session {user_id}..."
        )
        db_response_past_messages = await client.rpc(
            "match_user_messages",
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": match_count,
                "user_id_param": str(user_id),
            },
        ).execute()
        if db_response_past_messages.data:
            print(
                f"✅ [Semantic Memory] Found {len(db_response_past_messages.data)} similar past messages."
            )
            return db_response_past_messages.data

        return []

    except Exception as e:
        print(f"❌ [Semantic Memory] Error retrieving past messages: {e}")
        return []
