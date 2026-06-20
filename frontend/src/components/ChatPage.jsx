import { useState, useRef, useEffect } from "react";
import { getChatHistory } from "../api";

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const chatEndRef = useRef(null);
  const [useLangChain, setUseLangChain] = useState(true);
  const [chatId, setChatId] = useState(() => {
    const storageChatID = localStorage.getItem("current_chat_id");
    return storageChatID ? parseInt(storageChatID, 10) : null;
  });
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (chatId) {
      localStorage.setItem("current_chat_id", chatId.toString());
    }
  }, [chatId]);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!chatId) return;
      try {
        const data = await getChatHistory(chatId);
        if (data.status === "success") {
          setMessages(data.messages);
        }
      } catch (error) {
        console.error("Error fetching chat history:", error);
      }
    };

    fetchHistory();
  }, [chatId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();

    setMessages((prev) => [...prev, { sender: "user", text: userMessage }]);
    setInput("");
    setIsStreaming(true);

    setMessages((prev) => [...prev, { sender: "ai", text: "" }]);

    try {
      const targetUrl = useLangChain ? "/api/langchain/chat/stream" : "/api/chat/stream";
      const userId = import.meta.env.VITE_DEV_USER_ID;
      const response = await fetch(targetUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: userMessage, chat_id: chatId,user_id:userId }),
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      console.log("response:", response);

      const newChatId = response.headers.get("X-Chat-ID");
      if (newChatId && !chatId) {
        setChatId(parseInt(newChatId, 10));
        localStorage.setItem("current_chat_id", newChatId);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let aiTextRef = "";
      let lineBuffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        lineBuffer += decoder.decode(value, { stream: true });

        console.log(
          "📥 Raw Chunk Received from Backend:",
          JSON.stringify(lineBuffer)
        );

        const lines = lineBuffer.split("\n");
        lineBuffer = lines.pop() || "";

        let hasNewText = false;

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (trimmedLine.startsWith("data: ")) {
            const actualText = line.substring(6);
            aiTextRef += actualText;
            hasNewText = true;
          }
        }

        if (hasNewText) {
          setMessages((prev) => {
            const updated = [...prev];
            const aiMessageIndex = updated
              .map((m) => m.sender)
              .lastIndexOf("ai");

            if (aiMessageIndex !== -1) {
              updated[aiMessageIndex] = {
                ...updated[aiMessageIndex],
                text: aiTextRef,
              };
            }
            return updated;
          });
        }
      }
    } catch (error) {
      console.error("Stream API Error:", error);
      setMessages((prev) => {
        const updated = [...prev];

        const aiMessageIndex = updated.map((m) => m.sender).lastIndexOf("ai");

        if (aiMessageIndex !== -1) {
          updated[aiMessageIndex] = {
            sender: "ai",
            text: "An error occurred. Please try again.",
            isError: true,
          };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-900 text-slate-100 font-sans">
      <header className="py-4 px-6 bg-slate-800/50 border-b border-slate-700/50 backdrop-blur text-center">
        <h1 className="text-xl font-bold tracking-wide text-cyan-400">
          Gemini AI Assistant
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Powered by Flask & React (v4)
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 max-w-4xl w-full mx-auto ">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
            <span className="text-4xl">🤖</span>
            <p>Start a conversation with the AI assistant...</p>{" "}
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${
              msg.sender === "user" ? "  justify-end" : "justify-start"
            }`}
          >
            {msg.sender === "ai" &&
            !msg.text &&
            isStreaming &&
            index === messages.length - 1 ? (
              <div className="flex space-x-1.5 items-center py-1 px-2">
                <div
                  className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0ms" }}
                ></div>
                <div
                  className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
                  style={{ animationDelay: "150ms" }}
                ></div>
                <div
                  className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
                  style={{ animationDelay: "300ms" }}
                ></div>
              </div>
            ) : (
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm shadow-md leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-cyan-600 text-white rounded-br-none"
                    : msg.isError
                    ? "bg-red-950/50 border border-red-500/30 text-red-200 rounded-bl-none"
                    : "bg-slate-850 border border-slate-700/60 text-slate-200 rounded-b-none"
                }`}
              >
                <p className="whitespace-pre-wrap message-text" >{msg.text}</p>
              </div>
            )}
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      <footer className="p-4 bg-slate-900 border-t border-slate-800/60">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isStreaming}
            className="flex-1 bg-slate-800 border border-slate-700/80 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="bg-cyan-500 hover:bg-cyan-600 text-slate-900 font-semibold px-5 py-3 rounded-xl text-sm transition shadow-lg shadow-cyan-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </footer>
    </div>
  );
}
