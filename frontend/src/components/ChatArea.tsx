import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import MessageBubble from './MessageBubble';
import InputArea from './InputArea';
import { MessageSquare, GitMerge, Zap, Brain, Paperclip, Database } from 'lucide-react';

function ChatArea() {
  const {
    currentChatId,
    chats,
    currentMessages,
    isStreaming,
    streamingContent,
    error,
    setError,
  } = useStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const currentChat = chats.find((c) => c.id === currentChatId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages, isStreaming, streamingContent, error]);


  const handleTitleClick = () => {
    if (!currentChat) return;
    setEditingTitle(true);
    setNewTitle(currentChat.title || 'Untitled Chat');
  };

  const handleTitleSave = async () => {
    if (currentChat && newTitle && newTitle !== currentChat.title) {
      await useStore.getState().updateChatTitle(currentChatId!, newTitle);
    }
    setEditingTitle(false);
  };

  if (!currentChatId) {
    return (
      <div className="chat-area">
        <div className="landing">
          <div className="landing__hero">
            <div className="landing__logo">
              <GitMerge size={40} />
            </div>
            <h1 className="landing__title">ChatMerge</h1>
            <p className="landing__tagline">
              Chat with OpenAI, Anthropic, and Gemini — then merge your best conversations into one.
            </p>
          </div>

          <div className="landing__features">
            <div className="landing__feature">
              <div className="landing__feature-icon">
                <GitMerge size={20} />
              </div>
              <div className="landing__feature-content">
                <div className="landing__feature-title">Merge Any Chats</div>
                <div className="landing__feature-desc">
                  Combine conversations from different providers into a single thread. The AI retrieves semantically fused context from all merged chats via vector search.
                </div>
              </div>
            </div>

            <div className="landing__feature">
              <div className="landing__feature-icon">
                <Database size={20} />
              </div>
              <div className="landing__feature-content">
                <div className="landing__feature-title">RAG-Powered Context</div>
                <div className="landing__feature-desc">
                  Merged chats use vector retrieval to find the most relevant context — no more hitting token limits when conversations get long.
                </div>
              </div>
            </div>

            <div className="landing__feature">
              <div className="landing__feature-icon">
                <Brain size={20} />
              </div>
              <div className="landing__feature-content">
                <div className="landing__feature-title">Smart Vector Fusion</div>
                <div className="landing__feature-desc">
                  Merged chats use nearest-neighbor vector fusion — semantically overlapping content is averaged into single embeddings, unique content is preserved. Context scales infinitely.
                </div>
              </div>
            </div>

            <div className="landing__feature">
              <div className="landing__feature-icon">
                <Paperclip size={20} />
              </div>
              <div className="landing__feature-content">
                <div className="landing__feature-title">Files & Images</div>
                <div className="landing__feature-desc">
                  Drag-and-drop or paste images directly. Upload PDFs and code files. Attachments travel with messages through merges.
                </div>
              </div>
            </div>

            <div className="landing__feature">
              <div className="landing__feature-icon">
                <Zap size={20} />
              </div>
              <div className="landing__feature-content">
                <div className="landing__feature-title">Multi-Provider</div>
                <div className="landing__feature-desc">
                  One interface for GPT-4o, o4-mini, Claude Sonnet/Opus, and Gemini 2.0 Flash. Add your API keys in Settings to get started.
                </div>
              </div>
            </div>
          </div>

          <div className="landing__cta">
            <div className="landing__cta-text">
              <MessageSquare size={16} />
              <span>Create a new chat from the sidebar to get started</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-area">
      {currentChat && (
        <div className="chat-area__header">
          <div className="chat-area__title-section">
            {editingTitle ? (
              <input
                autoFocus
                className="chat-area__title-input"
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onBlur={handleTitleSave}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleTitleSave();
                  if (e.key === 'Escape') setEditingTitle(false);
                }}
              />
            ) : (
              <div className="chat-area__title" onClick={handleTitleClick}>
                {currentChat.title || 'Untitled Chat'}
              </div>
            )}
          </div>
          <div className="chat-area__model-info">
            {currentChat.is_merged && (
              <div className="model-badge" style={{
                background: 'rgba(34, 197, 94, 0.15)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
                color: '#4ade80',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 10px',
                borderRadius: '8px',
                fontSize: '12px',
                marginRight: '8px',
              }}>
                <Database size={12} />
                <span>RAG-powered</span>
              </div>
            )}
            <div className="model-badge">
              <div className="model-badge__provider">{currentChat.provider}</div>
              <div className="model-badge__model">{currentChat.model}</div>
            </div>
          </div>
        </div>
      )}

      <div className="chat-area__messages">
        {currentMessages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isStreaming && (
          <div className="message message--assistant">
            <div className="message__content">
              {streamingContent || ''}
              {!streamingContent && (
                <div className="message__typing">
                  <div className="message__typing-dot" />
                  <div className="message__typing-dot" />
                  <div className="message__typing-dot" />
                </div>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="message message--error" style={{
            padding: '12px 16px',
            margin: '8px 0',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '12px',
            color: '#fca5a5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '14px',
          }}>
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#fca5a5',
                cursor: 'pointer',
                fontSize: '18px',
                padding: '0 4px',
              }}
            >
              ×
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <InputArea />
    </div>
  );
}

export default ChatArea;
