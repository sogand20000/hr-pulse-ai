import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

export const sendChatMessage = async (payload) => {
  return await api.post("/chat", payload);
};
export const sendLangChainChatMessageStream = async (payload) => {
  const response = await api.post("langchain/chat/stream", payload);
  return response.data;
};
export const sendChatMessageStream = async (payload) => {
  const response = await api.post("/chat/stream", payload);
  return response.data;
};

export const getChatHistory = async (chatId) => {
  const response = await api.get(`/chat/${chatId}/history`);
  return response.data;
};
