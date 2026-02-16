import { useState, useEffect } from 'react';
import { useStore } from '../store';
import { PROVIDER_LABELS } from '../types';
import { X, Eye, EyeOff } from 'lucide-react';
import { api } from '../api';

function SettingsModal() {
  const { apiKeys, loadApiKeys, setShowSettings } = useStore();
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [loadingProviders, setLoadingProviders] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadApiKeys();
  }, []);

  const handleSaveKey = async (provider: string) => {
    const key = keyInputs[provider];
    if (!key.trim()) return;

    try {
      setLoadingProviders((prev) => ({ ...prev, [provider]: true }));
      await api.saveApiKey(provider, key);
      setKeyInputs((prev) => ({ ...prev, [provider]: '' }));
      await loadApiKeys();
    } catch (error) {
      console.error('Failed to save API key:', error);
    } finally {
      setLoadingProviders((prev) => ({ ...prev, [provider]: false }));
    }
  };

  const handleDeleteKey = async (keyId: string, provider: string) => {
    if (!window.confirm(`Delete ${provider} API key?`)) return;

    try {
      setLoadingProviders((prev) => ({ ...prev, [provider]: true }));
      await api.deleteApiKey(keyId);
      await loadApiKeys();
    } catch (error) {
      console.error('Failed to delete API key:', error);
    } finally {
      setLoadingProviders((prev) => ({ ...prev, [provider]: false }));
    }
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
          {providers.map(([key, label]) => {
            const existingKey = apiKeys.find((k) => k.provider === key);
            const isLoading = loadingProviders[key];

            return (
              <div key={key} className="settings-modal__section">
                <div className="settings-modal__section-title">
                  {label}
                </div>

                {existingKey ? (
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
                      onClick={() => handleDeleteKey(existingKey.id, key)}
                      disabled={isLoading}
                    >
                      {isLoading ? 'Deleting...' : 'Delete'}
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
                          disabled={isLoading}
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
                          disabled={isLoading}
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
                        disabled={!keyInputs[key]?.trim() || isLoading}
                      >
                        {isLoading ? 'Saving...' : 'Save'}
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
