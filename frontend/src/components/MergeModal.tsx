import { useState } from 'react';
import { useStore } from '../store';
import { LLM_PROVIDER_LABELS, PROVIDER_MODELS } from '../types';
import { X, Database } from 'lucide-react';

function MergeModal() {
  const {
    chats,
    mergeSelectedIds,
    isMerging,
    mergeProgress,
    ragEnabled,
    setShowMerge,
    toggleMergeSelect,
    startMerge,
    clearMergeSelection,
  } = useStore();

  const [mergeProvider, setMergeProvider] = useState('openai');
  const [mergeModel, setMergeModel] = useState('gpt-4o');

  const handleClose = () => {
    clearMergeSelection();
    setShowMerge(false);
  };

  const handleMerge = async () => {
    if (mergeSelectedIds.length < 2) return;
    await startMerge(mergeProvider, mergeModel);
  };

  const canMerge = mergeSelectedIds.length >= 2;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" style={{ maxWidth: '700px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <div className="modal__title">Merge Conversations</div>
            <div className="modal__subtitle">
              Select 2 or more chats to intelligently merge using AI
            </div>
          </div>
          <button className="modal__close" onClick={handleClose}>
            <X size={24} />
          </button>
        </div>

        <div className="modal__body">
          {!isMerging ? (
            <>
              {/* RAG Status Banner — only show when confirmed enabled */}
              {ragEnabled && (
                <div className="merge-modal__rag-status merge-modal__rag-status--enabled">
                  <Database size={14} />
                  <span>Smart fusion enabled — vector stores will be intelligently merged, not just concatenated</span>
                </div>
              )}

              <div className="merge-modal__chat-list">
                <div style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                  Select {2 - mergeSelectedIds.length} more chat{2 - mergeSelectedIds.length !== 1 ? 's' : ''} to merge
                </div>

                {chats.length === 0 ? (
                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                    No chats available to merge
                  </div>
                ) : (
                  chats.map((chat) => {
                    const isSelected = mergeSelectedIds.includes(chat.id);
                    const createdDate = new Date(chat.created_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    });

                    return (
                      <div
                        key={chat.id}
                        className={`merge-modal__chat-item ${
                          isSelected ? 'merge-modal__chat-item--selected' : ''
                        }`}
                        onClick={() => toggleMergeSelect(chat.id)}
                      >
                        <input
                          type="checkbox"
                          className="merge-modal__chat-checkbox"
                          checked={isSelected}
                          onChange={() => toggleMergeSelect(chat.id)}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <div className="merge-modal__chat-info">
                          <div className="merge-modal__chat-title">
                            {chat.title || 'Untitled Chat'}
                          </div>
                          <div className="merge-modal__chat-meta">
                            {chat.provider} • {chat.model} • {chat.message_count || 0} messages • {createdDate}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="merge-modal__model-selection">
                <label className="merge-modal__model-label">
                  Model to use for merge
                </label>
                <div className="merge-modal__model-selectors">
                  <select
                    className="model-selector"
                    value={mergeProvider}
                    onChange={(e) => {
                      setMergeProvider(e.target.value);
                      setMergeModel(PROVIDER_MODELS[e.target.value][0]);
                    }}
                  >
                    {Object.entries(LLM_PROVIDER_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <select
                    className="model-selector"
                    value={mergeModel}
                    onChange={(e) => setMergeModel(e.target.value)}
                  >
                    {PROVIDER_MODELS[mergeProvider].map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          ) : (
            <div>
              <div className="merge-modal__progress-header">
                <div className="merge-modal__spinner" />
                <span>Merging conversations using {mergeModel}...</span>
              </div>
              <div className="merge-modal__progress">{mergeProgress}</div>
            </div>
          )}
        </div>

        {!isMerging && (
          <div className="modal__footer">
            <button className="btn btn--secondary" onClick={handleClose}>
              Cancel
            </button>
            <button
              className="btn"
              onClick={handleMerge}
              disabled={!canMerge || isMerging}
            >
              {isMerging
                ? 'Merging...'
                : `Merge ${mergeSelectedIds.length} Chat${mergeSelectedIds.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default MergeModal;
