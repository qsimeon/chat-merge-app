import { Chat, Message, APIKeyInfo, MergeRequest, StreamChunk, Attachment } from './types';

const BASE_URL = '/api';

async function* streamFetch(url: string, body: Record<string, unknown>): AsyncGenerator<StreamChunk> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data as StreamChunk;
          } catch {
            // Skip malformed lines
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export const api = {
  // Chats
  async getChats(): Promise<Chat[]> {
    const response = await fetch(`${BASE_URL}/chats`);
    if (!response.ok) throw new Error('Failed to fetch chats');
    return response.json();
  },

  async createChat(data: {
    provider: string;
    model: string;
    title?: string;
    system_prompt?: string;
  }): Promise<Chat> {
    const response = await fetch(`${BASE_URL}/chats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create chat');
    return response.json();
  },

  async getChat(chatId: string): Promise<Chat> {
    const response = await fetch(`${BASE_URL}/chats/${chatId}`);
    if (!response.ok) throw new Error('Failed to fetch chat');
    return response.json();
  },

  async updateChat(
    chatId: string,
    data: { title?: string }
  ): Promise<Chat> {
    const response = await fetch(`${BASE_URL}/chats/${chatId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update chat');
    return response.json();
  },

  async deleteChat(chatId: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/chats/${chatId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete chat');
  },

  // Messages
  async getMessages(chatId: string): Promise<Message[]> {
    const response = await fetch(`${BASE_URL}/chats/${chatId}/messages`);
    if (!response.ok) throw new Error('Failed to fetch messages');
    return response.json();
  },

  // Streaming completion
  streamCompletion(chatId: string, content: string, attachmentIds?: string[]) {
    return streamFetch(`${BASE_URL}/chats/${chatId}/completions`, {
      content,
      attachment_ids: attachmentIds,
    });
  },

  // Attachments
  async uploadAttachments(files: File[]): Promise<Attachment[]> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const response = await fetch(`${BASE_URL}/attachments`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) throw new Error('Failed to upload attachments');
    return response.json();
  },

  getAttachmentUrl(attachmentId: string): string {
    return `${BASE_URL}/attachments/${attachmentId}`;
  },

  // API Keys
  async getApiKeys(): Promise<APIKeyInfo[]> {
    const response = await fetch(`${BASE_URL}/api-keys`);
    if (!response.ok) throw new Error('Failed to fetch API keys');
    return response.json();
  },

  async saveApiKey(provider: string, key: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/api-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: key }),
    });
    if (!response.ok) throw new Error('Failed to save API key');
  },

  async deleteApiKey(keyId: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/api-keys/${keyId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete API key');
  },

  // Merge
  streamMerge(data: MergeRequest) {
    return streamFetch(`${BASE_URL}/merge`, {
      chat_ids: data.chat_ids,
      merge_provider: data.merge_provider,
      merge_model: data.merge_model,
    });
  },

  // Models
  async getModels(): Promise<Record<string, string[]>> {
    const response = await fetch(`${BASE_URL}/models`);
    if (!response.ok) throw new Error('Failed to fetch models');
    return response.json();
  },
};
