import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import MessageBubble from './MessageBubble';
import InputArea from './InputArea';
import { MessageSquare } from 'lucide-react';

function ChatArea() {
  const {
    currentChatId,
    chats,
    currentMessages,
    isStreaming,
    streamingContent,
    streamingReasoning,
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
        <div className="chat-area__empty">
          <MessageSquare className="chat-area__empty-icon" />
          <div className="chat-area__empty-text">
            Select a chat or create a new one to get started
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
              {streamingReasoning && (
                <div className="message__reasoning">
                  <div style={{ fontSize: '12px', marginBottom: '8px' }}>
                    Reasoning: {streamingReasoning}
                  </div>
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
