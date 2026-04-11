import { Chat, Message, MergeRequest, StreamChunk, Attachment } from './types';

const BASE_URL = '/api';

// ─── Key storage (localStorage) ─────────────────────────────────────────────

const KEY_NAMES: Record<string, string> = {
  openai:    'chatmerge_key_openai',
  anthropic: 'chatmerge_key_anthropic',
  gemini:    'chatmerge_key_gemini',
  pinecone:  'chatmerge_key_pinecone',
};

export function getStoredKeys(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(KEY_NAMES).map(([provider, storageKey]) => [
      provider,
      localStorage.getItem(storageKey) || '',
    ])
  );
}

export function saveKey(provider: string, key: string): void {
  const storageKey = KEY_NAMES[provider];
  if (!storageKey) return;
  localStorage.setItem(storageKey, key.trim());
}

export function removeKey(provider: string): void {
  const storageKey = KEY_NAMES[provider];
  if (!storageKey) return;
  localStorage.removeItem(storageKey);
}

function keyHeaders(): Record<string, string> {
  const keys = getStoredKeys();
  const headers: Record<string, string> = {};
  if (keys.openai)    headers['x-openai-key']    = keys.openai;
  if (keys.anthropic) headers['x-anthropic-key'] = keys.anthropic;
  if (keys.gemini)    headers['x-google-key']    = keys.gemini;
  if (keys.pinecone)  headers['x-pinecone-key']  = keys.pinecone;
  return headers;
}

// ─── SSE streaming helper ────────────────────────────────────────────────────

async function* streamFetch(
  url: string,
  body: Record<string, unknown>,
  extraHeaders: Record<string, string> = {},
): AsyncGenerator<StreamChunk> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
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

// ─── API ─────────────────────────────────────────────────────────────────────

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
      headers: keyHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete chat');
  },

  // Messages
  async getMessages(chatId: string): Promise<Message[]> {
    const response = await fetch(`${BASE_URL}/chats/${chatId}/messages`);
    if (!response.ok) throw new Error('Failed to fetch messages');
    return response.json();
  },

  // Streaming completion — includes API keys as headers
  streamCompletion(chatId: string, content: string, attachmentIds?: string[]) {
    return streamFetch(
      `${BASE_URL}/chats/${chatId}/completions`,
      { content, attachment_ids: attachmentIds },
      keyHeaders(),
    );
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

  // Merge — includes API keys as headers
  streamMerge(data: MergeRequest) {
    return streamFetch(
      `${BASE_URL}/merge`,
      {
        chat_ids: data.chat_ids,
        merge_provider: data.merge_provider,
        merge_model: data.merge_model,
      },
      keyHeaders(),
    );
  },

  // Health check
  async getHealth(): Promise<{ status: string }> {
    const response = await fetch('/health');
    if (!response.ok) throw new Error('Failed to fetch health');
    return response.json();
  },

  // Models
  async getModels(): Promise<Record<string, string[]>> {
    const response = await fetch(`${BASE_URL}/models`);
    if (!response.ok) throw new Error('Failed to fetch models');
    return response.json();
  },
};
