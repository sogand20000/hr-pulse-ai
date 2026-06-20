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
    * **Google Gemini (gemini-3.5-flash):** The core Large Language Model used for text generation, configured with streaming enabled for a dynamic user experience.
* **Database & Vector Storage:** **Supabase (PostgreSQL)** acts as the central backbone:
    * Stores and syncs historical conversational logs.
    * Utilizes `pgvector` to perform highly accurate semantic similarity searches (`match_documents`) using `gemini-embedding-001`.
* **Resiliency Layer:** Integrated with **Tenacity** to guard streaming channels against transient network drops or API timeout failures.

---

## 🚀 Key Features

* **Real-time Streaming Responses:** Utilizes Server-Sent Events (SSE) via FastAPI's `StreamingResponse` to deliver instant, word-by-word text generation to the React frontend.
* **Context-Aware RAG Integration:** Automatically embeds user queries in real-time, queries the Supabase vector store, and injects relevant company documentation blocks into the LLM context window.
* **Intelligent History Synced Database:** Conversational histories are mapped into native LangChain Message schemas (`HumanMessage`/`AIMessage`) and dynamically updated back to Supabase without blocking the streaming UI.

---

## 🧠 Memory Management & Context Optimization

In LLM-based chat applications, sending the entire historical conversation with every new user request leads to exponential token costs and increased latency (TTFT). 

For this platform, I implemented a custom **Sliding Window (Buffer Window)** mechanism bounded by a configured size:

```python
window_size = 10
recent_messages = chat_history[-window_size:] if len(chat_history) > window_size else chat_history