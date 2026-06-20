# langchain_service.py

from backend.src.services.rag_service import (
    retrieve_relevant_context,
    retrieve_similar_past_messages,
)
from backend.src.services.supabase_service import (
    save_chat_message_vector,
    update_chat_history,
)
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", temperature=1.0, streaming=True
    )
except Exception as e:
    print(f"⚠️ Warning: Failed to initialize Gemini in LangChain: {e}")
    llm = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=6),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def execute_chain_with_retry(chain, input_data):
    """Executes the LangChain stream with an automatic retry mechanism."""
    return chain.astream(input_data)


async def get_langchain_rag_stream(
    user_message: str, chat_id: int, chat_history: list, user_id: int = None
):

    if not llm:
        raise ValueError("LangChain LLM is not initialized")

    window_size = 2
    recent_messages = (
        chat_history[-window_size:] if len(chat_history) > window_size else chat_history
    )

    formatted_memory = []
    for msg in recent_messages:
        role = msg.get("role")
        parts = msg.get("parts", [""])
        text_content = parts[0] if isinstance(parts, list) else str(parts)

        if role == "user":
            formatted_memory.append(HumanMessage(content=text_content))
        elif role in ["model", "assistant"]:
            formatted_memory.append(AIMessage(content=text_content))

    context_text = await retrieve_relevant_context(user_message)

    if not context_text:
        context_text = "No context found."

    past_conversations_text = "No relevant past conversations found."

    if user_id:
        similar_msgs = await retrieve_similar_past_messages(
            user_message, user_id, match_count=3, threshold=0.6
        )
        if similar_msgs:
            formatted_past = []
            for msg in similar_msgs:
                sender_label = (
                    "Employee" if msg.get("sender") == "user" else "HR Assistant"
                )
                formatted_past.append(f"- [{sender_label}]: {msg.get('message_text')}")
            past_conversations_text = "\n".join(formatted_past)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a professional AI HR assistant. Answer the user's question using the provided company document context"
                " and relevant past conversations from this specific employee (Semantic Memory) if available.\n\n"
                "[COMPANY DOCUMENT CONTEXT]\n{context}\n\n"
                "[EMPLOYEE'S PAST RELEVANT CONVERSATIONS (CROSS-SESSION)]\n{past_context}",
            ),
            MessagesPlaceholder(variable_name="history_placeholder"),
            ("human", "{question}"),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    full_ai_response = ""

    try:
        async_stream = await execute_chain_with_retry(
            chain,
            {
                "context": context_text,
                "past_context": past_conversations_text,
                "question": user_message,
                "history_placeholder": formatted_memory,
            },
        )

        async for chunk in async_stream:
            if chunk:
                text_chunk = str(chunk)
                full_ai_response += text_chunk
                yield f"data: {text_chunk}\n\n"

    except Exception as stream_err:
        print(f"❌ Critical: Chain execution failed after retries: {stream_err}")
        raise stream_err

    finally:
        try:
            print(
                f"📋 [Finally] Raw chat_history content before sync: {chat_history}",
                flush=True,
            )
            is_user_last = False
            if chat_history and len(chat_history) > 0:
                last_msg = chat_history[-1]
                if isinstance(last_msg, dict):
                    is_user_last = (
                        last_msg.get("role") == "user"
                        or last_msg.get("type") == "human"
                    )
                else:
                    is_user_last = getattr(last_msg, "type", "") == "human"
            if not is_user_last:
                chat_history.append({"role": "user", "parts": [user_message]})

            if full_ai_response:
                chat_history.append({"role": "model", "parts": [full_ai_response]})
            print(
                f"⏳ [Finally] Syncing history locally. Total items: {len(chat_history)}. Updating Supabase...",
                flush=True,
            )

            db_res = await update_chat_history(chat_id, chat_history)
            if db_res and hasattr(db_res, "data"):
                print(
                    f"✅ [Finally] History successfully synced in DB for chat ID {chat_id}",
                    flush=True,
                )
            else:
                print(
                    f"⚠️ [Finally] WARNING: Update query executed successfully, BUT affected 0 rows! Check if chat_id '{chat_id}' actually exists in 'chats' table.",
                    flush=True,
                )

            if full_ai_response:
                print(
                    "⏳ [Finally] Saving message vectors to database...",
                    flush=True,
                )
                await save_chat_message_vector(chat_id, "user", user_message)
                await save_chat_message_vector(chat_id, "model", full_ai_response)
                print("✅ [Finally] All message vectors processed.", flush=True)

        except Exception as db_err:
            print(f"⚠️ Non-blocking database sync failure: {db_err}")
