import asyncio

from backend.src.services.rag_service import retrieve_relevant_context
from backend.src.services.supabase_service import update_chat_history
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash", temperature=1.0, streaming=True
    )
except Exception as e:
    print(f"⚠️ Warning: Failed to initialize Gemini in LangChain: {e}")
    llm = None


async def get_langchain_rag_stream(user_message: str, chat_id: int, chat_history: list):

    if not llm:
        raise ValueError("LangChain LLM is not initialized")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer the user's question using the provided context below. "
                "If the context does not contain the answer, rely on your general knowledge "
                "but state clearly that it wasn't found in the documents.\n\n"
                "[CONTEXT]\n{context}",
            ),
            MessagesPlaceholder(variable_name="history_placeholder"),
            ("human", "{question}"),
        ]
    )

    formatted_memory = []
    for msg in chat_history:
        role = msg.get("role")
        parts = msg.get("parts", [""])
        text_content = parts[0] if isinstance(parts, list) else str(parts)

        if role == "user":
            formatted_memory.append(HumanMessage(content=text_content))
        elif role in ["model", "assistant"]:
            formatted_memory.append(AIMessage(content=text_content))

    context_text = await asyncio.to_thread(retrieve_relevant_context, user_message)

    if not context_text:
        context_text = "No context found."

    chat_history.append({"role": "user", "parts": [user_message]})

    chain = prompt | llm | StrOutputParser()

    full_ai_response = ""
    try:
        async_stream = chain.astream(
            {
                "context": context_text,
                "question": user_message,
                "history_placeholder": formatted_memory,
            }
        )

        async for chunk in async_stream:
            if chunk:
                text_chunk = str(chunk)
                full_ai_response += text_chunk
                yield f"data: {text_chunk}\n\n"
    except Exception as stream_err:
        print(f"❌ Error during chain astream: {stream_err}")
        raise stream_err

    finally:
        if chat_id and full_ai_response:
            try:
                chat_history.append({"role": "model", "parts": [full_ai_response]})
                await asyncio.to_thread(update_chat_history, chat_id, chat_history)
                print("✅ LangChain DB updated successfully!\n")

            except Exception as db_err:
                print(f"⚠️ Failed to save messages to Supabase: {db_err}")
