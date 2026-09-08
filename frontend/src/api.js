import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: 60000,
});

export const api = {
  getDocuments: async (chatId = null) => {
    const params = {};
    if (chatId) params.chat_id = chatId;
    const res = await client.get('/documents', { params });
    return res.data;
  },

  getDocumentsStatus: async (chatId = null) => {
    const params = {};
    if (chatId) params.chat_id = chatId;
    const res = await client.get('/documents/status', { params });
    return res.data;
  },

  getDocument: async (docId) => {
    const res = await client.get(`/documents/${docId}`);
    return res.data;
  },

  uploadDocuments: async (fileList, chatId = null) => {
    const formData = new FormData();
    for (let i = 0; i < fileList.length; i++) {
      formData.append('files', fileList[i]);
    }
    const params = {};
    if (chatId) params.chat_id = chatId;
    const res = await client.post('/upload', formData, { params });
    return res.data;
  },

  getFacts: async (documentId = null, chatId = null) => {
    const params = {};
    if (documentId) params.document_id = documentId;
    if (chatId) params.chat_id = chatId;
    const res = await client.get('/facts', { params });
    return res.data;
  },

  getRelationships: async (type = null, chatId = null) => {
    const params = {};
    if (type) params.type = type;
    if (chatId) params.chat_id = chatId;
    const res = await client.get('/relationships', { params });
    return res.data;
  },

  getPdfUrl: (filename) => {
    return `${API_BASE}/api/pdf/${encodeURIComponent(filename)}`;
  },

  getChats: async () => {
    const res = await client.get('/chats');
    return res.data;
  },

  getChat: async (chatId) => {
    const res = await client.get(`/chats/${chatId}`);
    return res.data;
  },

  createChat: async (title) => {
    const res = await client.post('/chats', { title });
    return res.data;
  },

  deleteChat: async (chatId) => {
    const res = await client.delete(`/chats/${chatId}`);
    return res.data;
  },

  updateChat: async (chatId, title) => {
    const res = await client.patch(`/chats/${chatId}`, { title });
    return res.data;
  },

  sendChatMessage: async (chatId, content, documentId = null) => {
    const res = await client.post(`/chats/${chatId}/messages`, { content });
    return res.data;
  },
};

