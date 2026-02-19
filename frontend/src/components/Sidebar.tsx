import { useState } from 'react';
import { useStore } from '../store';
import { LLM_PROVIDER_LABELS, PROVIDER_MODELS } from '../types';
import { Plus, Settings, Trash2, GitMerge } from 'lucide-react';

function Sidebar() {
  const {
    chats,
    currentChatId,
    showSettings,
    showMerge,
    mergeSelectedIds,
    selectChat,
    createChat,
    deleteChat,
    setShowSettings,
    setShowMerge,
    toggleMergeSelect,
  } = useStore();

  const [showNewChatForm, setShowNewChatForm] = useState(false);
  const [newChatProvider, setNewChatProvider] = useState('openai');
  const [newChatModel, setNewChatModel] = useState('gpt-4o');

  const handleCreateChat = async () => {
    await createChat(newChatProvider, newChatModel);
    setShowNewChatForm(false);
    setNewChatProvider('openai');
    setNewChatModel('gpt-4o');
  };

  const handleChatItemClick = (e: React.MouseEvent, chatId: string) => {
    if (showMerge) {
      e.preventDefault();
      toggleMergeSelect(chatId);
    } else {
      selectChat(chatId);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    if (window.confirm('Delete this chat?')) {
      deleteChat(chatId);
    }
  };

  const canMerge = chats.length >= 2;
  const isMergeMode = showMerge;

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <div className="sidebar__title">ChatMerge</div>
        <div className="sidebar__actions">
          <button
            className="sidebar__btn"
            onClick={() => setShowSettings(!showSettings)}
            title="Settings"
          >
            <Settings size={20} />
          </button>
        </div>
      </div>

      {!isMergeMode && (
        <div className="sidebar__new-chat-section">
          {!showNewChatForm ? (
            <button className="btn" onClick={() => setShowNewChatForm(true)}>
              <Plus size={18} />
              New Chat
            </button>
          ) : (
            <div className="sidebar__new-chat-form">
              <div className="new-chat-form__inputs">
                <select
                  className="model-selector"
                  value={newChatProvider}
                  onChange={(e) => {
                    setNewChatProvider(e.target.value);
                    setNewChatModel(PROVIDER_MODELS[e.target.value][0]);
                  }}
                >
                  {Object.entries(LLM_PROVIDER_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="new-chat-form__inputs">
                <select
                  className="model-selector"
                  value={newChatModel}
                  onChange={(e) => setNewChatModel(e.target.value)}
                >
                  {PROVIDER_MODELS[newChatProvider].map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>
              <div className="new-chat-form__buttons">
                <button className="btn" onClick={handleCreateChat}>
                  Create
                </button>
                <button
                  className="btn btn--secondary"
                  onClick={() => setShowNewChatForm(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="sidebar__chat-list">
        {chats.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            No chats yet. Create one to get started!
          </div>
        ) : (
          chats.map((chat) => {
            const isSelected = currentChatId === chat.id;
            const isMergeSelected = mergeSelectedIds.includes(chat.id);

            return (
              <div
                key={chat.id}
                className={`sidebar__chat-item ${
                  isSelected && !isMergeMode ? 'sidebar__chat-item--active' : ''
                }`}
                style={
                  isMergeMode && isMergeSelected
                    ? { background: 'var(--accent)', color: 'white' }
                    : undefined
                }
                onClick={(e) => handleChatItemClick(e, chat.id)}
              >
                <div className="chat-item__header">
                  {isMergeMode && (
                    <input
                      type="checkbox"
                      className="chat-item__checkbox"
                      checked={isMergeSelected}
                      onChange={() => toggleMergeSelect(chat.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
                  <div className="chat-item__title">
                    {chat.title || 'Untitled Chat'}
                  </div>
                  {!isMergeMode && (
                    <button
                      className="chat-item__delete-btn"
                      onClick={(e) => handleDeleteClick(e, chat.id)}
                      title="Delete chat"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
                <div className="chat-item__meta">
                  <span className="chat-item__provider">
                    {chat.provider} • {chat.model}
                  </span>
                  <span>{chat.message_count || 0} msgs</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {!isMergeMode && canMerge && (
        <button className="btn sidebar__merge-btn" onClick={() => setShowMerge(true)}>
          <GitMerge size={18} />
          Merge Chats
        </button>
      )}
    </div>
  );
}

export default Sidebar;
