import { create } from 'zustand';
import { Chat, Message, APIKeyInfo } from './types';
import { api } from './api';

export interface AppState {
  // Data
  chats: Chat[];
  currentChatId: string | null;
  currentMessages: Message[];
  apiKeys: APIKeyInfo[];

  // UI state
  isLoading: boolean;
  isStreaming: boolean;
  streamingContent: string;
  streamingReasoning: string;
  error: string | null;

  // Modal state
  showSettings: boolean;
  showMerge: boolean;
  mergeSelectedIds: string[];
  isMerging: boolean;
  mergeProgress: string;

  // Actions
  loadChats: () => Promise<void>;
  selectChat: (chatId: string) => Promise<void>;
  createChat: (provider: string, model: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  updateChatTitle: (chatId: string, title: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  loadApiKeys: () => Promise<void>;

  // Merge
  toggleMergeSelect: (chatId: string) => void;
  startMerge: (provider: string, model: string) => Promise<void>;

  // UI
  setShowSettings: (show: boolean) => void;
  setShowMerge: (show: boolean) => void;
  setError: (error: string | null) => void;
  clearMergeSelection: () => void;
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  chats: [],
  currentChatId: null,
  currentMessages: [],
  apiKeys: [],
  isLoading: false,
  isStreaming: false,
  streamingContent: '',
  streamingReasoning: '',
  error: null,
  showSettings: false,
  showMerge: false,
  mergeSelectedIds: [],
  isMerging: false,
  mergeProgress: '',

  // Actions
  loadChats: async () => {
    try {
      set({ isLoading: true, error: null });
      const chats = await api.getChats();
      set({ chats });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to load chats' });
    } finally {
      set({ isLoading: false });
    }
  },

  selectChat: async (chatId: string) => {
    try {
      set({ currentChatId: chatId, isLoading: true, error: null });
      const chat = await api.getChat(chatId);
      const messages = await api.getMessages(chatId);
      set({ currentMessages: messages });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to load chat' });
    } finally {
      set({ isLoading: false });
    }
  },

  createChat: async (provider: string, model: string) => {
    try {
      set({ isLoading: true, error: null });
      const chat = await api.createChat({ provider, model });
      set((state) => ({
        chats: [chat, ...state.chats],
        currentChatId: chat.id,
        currentMessages: [],
      }));
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to create chat' });
    } finally {
      set({ isLoading: false });
    }
  },

  deleteChat: async (chatId: string) => {
    try {
      set({ error: null });
      await api.deleteChat(chatId);
      set((state) => {
        const newChats = state.chats.filter((c) => c.id !== chatId);
        const newCurrentChatId =
          state.currentChatId === chatId
            ? newChats.length > 0
              ? newChats[0].id
              : null
            : state.currentChatId;
        return {
          chats: newChats,
          currentChatId: newCurrentChatId,
          currentMessages: newCurrentChatId === state.currentChatId ? state.currentMessages : [],
        };
      });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to delete chat' });
    }
  },

  updateChatTitle: async (chatId: string, title: string) => {
    try {
      set({ error: null });
      await api.updateChat(chatId, { title });
      set((state) => ({
        chats: state.chats.map((c) => (c.id === chatId ? { ...c, title } : c)),
      }));
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to update chat' });
    }
  },

  sendMessage: async (content: string) => {
    const state = get();
    if (!state.currentChatId) return;

    try {
      set({ error: null, isStreaming: true, streamingContent: '', streamingReasoning: '' });

      // Add user message optimistically
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        chat_id: state.currentChatId,
        role: 'user',
        content,
        reasoning_trace: null,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        currentMessages: [...state.currentMessages, userMessage],
      }));

      let assistantContent = '';
      let assistantReasoning = '';

      // Stream completion
      for await (const chunk of api.streamCompletion(state.currentChatId, content)) {
        if (chunk.type === 'content') {
          assistantContent += chunk.data;
          set((state) => ({
            streamingContent: assistantContent,
          }));
        } else if (chunk.type === 'reasoning') {
          assistantReasoning += chunk.data;
          set((state) => ({
            streamingReasoning: assistantReasoning,
          }));
        } else if (chunk.type === 'done') {
          // Add complete assistant message
          const assistantMessage: Message = {
            id: chunk.data,
            chat_id: state.currentChatId,
            role: 'assistant',
            content: assistantContent,
            reasoning_trace: assistantReasoning || null,
            created_at: new Date().toISOString(),
          };

          set((state) => ({
            currentMessages: state.currentMessages.map((m) =>
              m.id === userMessage.id ? userMessage : m
            ),
          }));

          set((state) => ({
            currentMessages: [...state.currentMessages, assistantMessage],
          }));
        } else if (chunk.type === 'error') {
          set({ error: chunk.data });
        }
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to send message' });
    } finally {
      set({
        isStreaming: false,
        streamingContent: '',
        streamingReasoning: '',
      });
      // Refresh chats list to update message counts
      await get().loadChats();
    }
  },

  loadApiKeys: async () => {
    try {
      set({ error: null });
      const apiKeys = await api.getApiKeys();
      set({ apiKeys });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to load API keys' });
    }
  },

  toggleMergeSelect: (chatId: string) => {
    set((state) => {
      const isSelected = state.mergeSelectedIds.includes(chatId);
      return {
        mergeSelectedIds: isSelected
          ? state.mergeSelectedIds.filter((id) => id !== chatId)
          : [...state.mergeSelectedIds, chatId],
      };
    });
  },

  startMerge: async (provider: string, model: string) => {
    const state = get();
    if (state.mergeSelectedIds.length < 2) {
      set({ error: 'Select at least 2 chats to merge' });
      return;
    }

    try {
      set({ error: null, isMerging: true, mergeProgress: '' });

      let mergedChatId = '';

      for await (const chunk of api.streamMerge({
        chat_ids: state.mergeSelectedIds,
        merge_provider: provider,
        merge_model: model,
      })) {
        if (chunk.type === 'content') {
          set((state) => ({
            mergeProgress: state.mergeProgress + chunk.data,
          }));
        } else if (chunk.type === 'merge_complete') {
          mergedChatId = chunk.data;
        } else if (chunk.type === 'error') {
          set({ error: chunk.data });
        }
      }

      // Load merged chat
      if (mergedChatId) {
        set({ mergeProgress: 'Opening merged chat...' });
        await new Promise((resolve) => setTimeout(resolve, 1000));

        set((state) => ({
          showMerge: false,
          mergeSelectedIds: [],
          isMerging: false,
          mergeProgress: '',
        }));

        // Refresh chats list and open merged chat
        await get().loadChats();
        await get().selectChat(mergedChatId);
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to merge chats' });
    } finally {
      set({ isMerging: false });
    }
  },

  setShowSettings: (show: boolean) => {
    set({ showSettings: show });
  },

  setShowMerge: (show: boolean) => {
    set({ showMerge: show, mergeSelectedIds: [] });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  clearMergeSelection: () => {
    set({ mergeSelectedIds: [] });
  },
}));
