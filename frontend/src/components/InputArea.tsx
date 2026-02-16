import { useState, useRef, useEffect } from 'react';
import { useStore } from '../store';
import { Send } from 'lucide-react';

function InputArea() {
  const { currentChatId, isStreaming, sendMessage } = useStore();
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        200
      ) + 'px';
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || !currentChatId || isStreaming) return;

    const message = input.trim();
    setInput('');
    await sendMessage(message);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-area__input-section">
      <div className="input-area">
        <div className="input-area__wrapper">
          <textarea
            ref={textareaRef}
            className="input-area__textarea"
            placeholder="Type your message... (Shift+Enter for new line)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming || !currentChatId}
            rows={1}
          />
          <button
            className="input-area__send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isStreaming || !currentChatId}
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default InputArea;
