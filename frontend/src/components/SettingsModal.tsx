import { useState } from 'react';
import { useStore } from '../store';
import { PROVIDER_LABELS } from '../types';
import { X, Eye, EyeOff } from 'lucide-react';

function SettingsModal() {
  const { savedProviders, saveApiKey, deleteApiKey, setShowSettings } = useStore();
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  const handleSaveKey = (provider: string) => {
    const key = keyInputs[provider];
    if (!key?.trim()) return;
    saveApiKey(provider, key.trim());
    setKeyInputs((prev) => ({ ...prev, [provider]: '' }));
  };

  const handleDeleteKey = (provider: string) => {
    const label = PROVIDER_LABELS[provider] || provider;
    if (!window.confirm(`Remove ${label} API key?`)) return;
    deleteApiKey(provider);
  };

  const providers = Object.entries(PROVIDER_LABELS);

  return (
    <div className="modal-overlay" onClick={() => setShowSettings(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <div className="modal__title">Settings</div>
            <div className="modal__subtitle">Manage your API keys</div>
          </div>
          <button
            className="modal__close"
            onClick={() => setShowSettings(false)}
          >
            <X size={24} />
          </button>
        </div>

        <div className="modal__body">
          <div style={{
            fontSize: '12px',
            color: 'var(--text-tertiary)',
            marginBottom: '16px',
            lineHeight: '1.5',
            padding: '8px 12px',
            background: 'rgba(139, 92, 246, 0.08)',
            borderRadius: '6px',
          }}>
            Keys are stored in your browser only — never sent to the server except as encrypted request headers during API calls.
          </div>

          {providers.map(([key, label]) => {
            const hasKey = savedProviders.includes(key);

            return (
              <div key={key} className="settings-modal__section">
                <div className="settings-modal__section-title">
                  {label}
                </div>
                {key === 'pinecone' && (
                  <div style={{
                    fontSize: '12px',
                    color: 'var(--text-tertiary)',
                    marginBottom: '8px',
                    lineHeight: '1.5',
                  }}>
                    Enables smart vector fusion for merged chats. Requires an <strong style={{ color: 'var(--text-secondary)' }}>OpenAI</strong> or <strong style={{ color: 'var(--text-secondary)' }}>Gemini</strong> key to generate embeddings.
                  </div>
                )}

                {hasKey ? (
                  <div className="settings-modal__api-key-row">
                    <div className="settings-modal__api-key-info">
                      <div className="settings-modal__api-key-provider">
                        {label}
                      </div>
                      <div className="settings-modal__api-key-status settings-modal__api-key-status--active">
                        ✓ Key configured
                      </div>
                    </div>
                    <button
                      className="btn btn--danger"
                      onClick={() => handleDeleteKey(key)}
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <div className="api-key-input">
                    <div className="api-key-input__field">
                      <label className="api-key-input__label">
                        Enter your {label} API key
                      </label>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type={showKeys[key] ? 'text' : 'password'}
                          className="api-key-input__input"
                          placeholder={`${label} API key...`}
                          value={keyInputs[key] || ''}
                          onChange={(e) =>
                            setKeyInputs((prev) => ({
                              ...prev,
                              [key]: e.target.value,
                            }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveKey(key);
                          }}
                        />
                        <button
                          className="api-key-input__toggle"
                          onClick={() =>
                            setShowKeys((prev) => ({
                              ...prev,
                              [key]: !prev[key],
                            }))
                          }
                          type="button"
                        >
                          {showKeys[key] ? (
                            <EyeOff size={18} />
                          ) : (
                            <Eye size={18} />
                          )}
                        </button>
                      </div>
                    </div>
                    <div className="api-key-input__buttons">
                      <button
                        className="btn"
                        onClick={() => handleSaveKey(key)}
                        disabled={!keyInputs[key]?.trim()}
                      >
                        Save
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="modal__footer">
          <button className="btn btn--secondary" onClick={() => setShowSettings(false)}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
