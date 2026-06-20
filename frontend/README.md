# 🧠 HR-Pulse.AI | Enterprise RAG Chatbot Platform

**HR-Pulse.AI** is a domain-agnostic, high-performance **RAG-powered AI Chatbot** designed to act as an intelligent knowledge base assistant. While pre-configured in this repository with an **Enterprise Human Resources (HR) & Internal Policy** use-case, the core architecture is entirely dynamic. The chatbot's expertise automatically adapts to whatever knowledge base or documentation is injected into its vector database.

Instead of relying on generic AI knowledge, this chatbot utilizes a modern **Retrieval-Augmented Generation (RAG)** architecture. This ensures that every response is strictly grounded in the organization's official documentation, eliminating hallucinations and ensuring data trustworthiness.

---

## 🏗️ Core Architecture & Tech Stack

The application is split into a modular, decoupled architecture optimized for speed, scalability, and network resilience:

* **Frontend:** Built with **React** to deliver a smooth, intuitive, and responsive chat interface for the users.
* **Backend API:** Powered by **FastAPI (Python)**, leveraging asynchronous programming (`async/await`) to handle high-concurrency streaming effortlessly.
* **AI & Orchestration Ecosystem:**
    * **LangChain (LCEL):** Used to construct clean, industrial LLM chains and prompt templates.
    * **Google Gemini (gemini-2.5-flash):** The core Large Language Model used for text generation, configured with streaming enabled for a dynamic user experience.
* **Database & Vector Storage:** **Supabase (PostgreSQL)** acts as the central backbone:
    * Stores and syncs historical conversational logs.
    * Utilizes `pgvector` to perform highly accurate semantic similarity searches (`match_documents`) using `gemini-embedding-001`.
* **Resiliency Layer:** Integrated with **Tenacity** to guard streaming channels against transient network drops or API timeout failures.

---

## 🚀 Key Features

* **Real-time Streaming Responses:** Utilizes Server-Sent Events (SSE) via FastAPI's `StreamingResponse` to deliver instant, word-by-word text generation to the React frontend.
* **Context-Aware RAG Integration:** Automatically embeds user queries in real-time, queries the Supabase vector store, and injects relevant company documentation blocks into the LLM context window.
* **Cross-Session Semantic Memory:** Remembers user-specific details (e.g., name, age, preferences) shared in older, completely separate chat sessions, preventing the LLM from experiencing context amnesia across chat switches.
* **Intelligent History Synced Database:** Conversational histories are mapped into native LangChain Message schemas (`HumanMessage`/`AIMessage`) and dynamically updated back to Supabase without blocking the streaming UI.
---

## 🗄️ Database Schema & Data Models

The platform leverages **Supabase (PostgreSQL)** with the `pgvector` extension to store knowledge base documents, manage user sessions, and maintain vector-embedded chat histories. 

Below is the entity-relationship architecture visualization from the Supabase Schema Visualizer:

```text
               ┌──────────────────────────┐
               │        documents         │
               ├──────────────────────────┤
               │ id (PK)                  │
               │ content [text]           │
               │ metadata [jsonb]         │
               │ embedding [vector]       │
               └──────────────────────────┘

┌──────────────────────────┐           ┌──────────────────────────┐
│  chat_messages_vectors   │           │          chats           │
├──────────────────────────┤           ├──────────────────────────┤
│ id (PK) [int8]           │           │ id (PK) [int8]           │
│ session_id (FK) [int8] ──┼──────────►│ user_id [uuid]           │
│ sender [text]            │           │ history [jsonb]          │
│ message_text [text]      │           │ created_at [timestamptz] │
│ embedding [vector]       │           └──────────────────────────┘
│ created_at [timestamptz] │
└──────────────────────────┘
```
---


## 🧠 Memory Management & Context Optimization

In LLM-based chat applications, sending the entire historical conversation with every new user request leads to exponential token costs and increased Time-To-First-Token (TTFT) latency. 

To overcome this, this platform implements an advanced **Two-Tier Hybrid Memory Architecture** that guarantees both immediate flow and long-term personalization:

### 1. Short-Term Memory (Sliding Window Buffer)
For the active chat session, the chat history is constrained by a sliding window mechanism. Only the most recent messages are passed linearly into the immediate prompt conversation array, keeping token overhead at a bare minimum while maintaining conversational continuity:



### 2. Long-Term Semantic Memory (Cross-Session Knowledge)
When a user opens a brand new chat session, the short-term sliding window is naturally empty ([]). To prevent the chatbot from losing all user context, an asynchronous vector search layer is triggered globally across all historic chats belonging to that specific User UUID.

The backend invokes a custom Supabase PostgreSQL RPC function match_user_messages to fetch historically relevant facts or profile points previously stated by the employee:

``` sql
create or replace function public.match_user_messages (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  user_id_param uuid
)
returns table (id bigint, session_id bigint, sender text, message_text text, similarity float)
language plpgsql as $$
begin
  return query
  select v.id, v.session_id, v.sender, v.message_text, 1 - (v.embedding <=> query_embedding) as similarity
  from chat_messages_vectors v
  inner join chats c on v.session_id = c.id
  where c.user_id = user_id_param and 1 - (v.embedding <=> query_embedding) > match_threshold
  order by v.embedding <=> query_embedding asc
  limit match_count;
end;
$$;
```


 ### 🔄 Context Fusion Lifecycle
 
Whenever a user submits a query, the context undergoes a unified compilation before hitting the Gemini API:

```
[User Query]
     │
     ├───► Vector Search (Company Docs) ───► [COMPANY DOCUMENT CONTEXT] ───┐
     │                                                                     ├───► [Fused Gemini Prompt]
     ├───► Vector Search (User History) ───► [SEMANTIC MEMORY CONTEXT]  ───┤
     │                                                                     │
     └───► Linear Active History        ───► [SHORT-TERM SLIDING WINDOW] ──┘

```

This hybrid approach ensures that if a user states their name or age in Chat #1, and later asks an unrelated policy question in Chat #2, the system seamlessly recalls their user metadata from the vector space and crafts a tailored, contextual response without blowing up the token window.