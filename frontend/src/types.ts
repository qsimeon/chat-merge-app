export interface Chat {
  id: string;
  title: string | null;
  provider: string;
  model: string;
  system_prompt: string | null;
  is_merged?: boolean;
  created_at: string;
  updated_at: string;
  message_count?: number;
  messages?: Message[];
}

export interface Attachment {
  id: string;
  message_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  storage_path: string;
  created_at: string;
}

export interface Message {
  id: string;
  chat_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  attachments?: Attachment[];
}

export interface APIKeyInfo {
  id: string;
  provider: string;
  is_active: boolean;
  created_at: string;
}

export interface MergeRequest {
  chat_ids: string[];
  merge_provider: string;
  merge_model: string;
}

export interface StreamChunk {
  type: 'content' | 'done' | 'error' | 'merge_complete' | 'warning';
  data: string;
}

export type Provider = 'openai' | 'anthropic' | 'gemini';

export const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1', 'o1-mini'],
  anthropic: ['claude-sonnet-4-20250514', 'claude-haiku-4-20250414', 'claude-opus-4-20250514'],
  gemini: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
};

// All API key providers (used in Settings modal)
export const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  gemini: 'Google Gemini',
  pinecone: 'Pinecone (RAG)',
};

// LLM providers only — Pinecone is a vector store, not a chat model (used in merge/chat UI)
export const LLM_PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  gemini: 'Google Gemini',
};
