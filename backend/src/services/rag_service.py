# rag_service.py
import os

from backend.src.services.supabase_service import get_supabase_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")

ai_client = genai.Client(api_key=api_key)


def get_embedding(text: str, is_query: bool = False):
    task = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    try:
        response = ai_client.models.embed_content(
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
    query: str, match_count: int = None, threshold: float = None
) -> str:

    if match_count is None:
        env_count = os.environ.get("RAG_MATCH_COUNT")
        match_count = int(env_count) if env_count else 3

    if threshold is None:
        env_threshold = os.environ.get("RAG_MATCH_THRESHOLD")
        threshold = float(env_threshold) if env_threshold else 0.4

    try:
        response = ai_client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY", output_dimensionality=768
            ),
        )

        if not response.embeddings:
            return ""

        query_embedding = response.embeddings[0].values
        print(
            f"⏳ [RAG] Calling match_documents in Supabase (Threshold: {threshold})..."
        )
        client = await get_supabase_client()
        db_response = await client.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": match_count,
            },
        ).execute()
        print(f"📊 [RAG] Database raw response: {db_response.data}")
        if db_response.data and len(db_response.data) > 0:
            for i, row in enumerate(db_response.data):
                print(
                    f"📌 Match #{i + 1}: ID={row['id']} | Similarity={row.get('similarity')}  | Text={row['content'][:30]}..."
                )

            context_list = [row["content"] for row in db_response.data]
            return "\n\n---\n\n".join(context_list)

        print("🔍 [RAG] No relevant context met the threshold in database.")
        return ""

    except Exception as e:
        print(f"❌ [RAG] Error during retrieval: {e}")
        return ""


async def retrieve_similar_past_messages(
    query: str, user_id: int, match_count: int = 3, threshold: float = 0.5
) -> list:
    try:
        print(
            "⏳ [Semantic Memory] Generating async embedding for past message match..."
        )

        response = await ai_client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY", output_dimensionality=768
            ),
        )
        if not response.embeddings:
            return []
        query_embedding = response.embeddings[0].values
        client = await get_supabase_client()

        print(
            f"⏳ [Semantic Memory] Calling match_chat_messages RPC for session {user_id}..."
        )
        db_response = await client.rpc(
            "match_user_messages",
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": match_count,
                "user_id_param": str(user_id),
            },
        ).execute()
        if db_response.data:
            print(
                f"✅ [Semantic Memory] Found {len(db_response.data)} similar past messages."
            )
            return db_response.data

        return []

    except Exception as e:
        print(f"❌ [Semantic Memory] Error retrieving past messages: {e}")
        return []
