import { useState, useRef, useEffect } from 'react';
import { useStore } from '../store';
import { Send, Paperclip, X, FileText, Image as ImageIcon } from 'lucide-react';

interface FilePreview {
  file: File;
  preview?: string;
}

function InputArea() {
  const { currentChatId, isStreaming, sendMessage } = useStore();
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<FilePreview[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  // Cleanup previews when files change
  useEffect(() => {
    return () => {
      files.forEach(f => {
        if (f.preview) URL.revokeObjectURL(f.preview);
      });
    };
  }, [files]);

  const handleSend = async () => {
    if ((!input.trim() && files.length === 0) || !currentChatId || isStreaming) return;

    const message = input.trim();
    const fileList = files.map(f => f.file);

    setInput('');
    setFiles([]);

    await sendMessage(message, fileList);

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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    addFiles(selectedFiles);
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const addFiles = (newFiles: File[]) => {
    const filePreviews: FilePreview[] = newFiles.map(file => {
      const preview = file.type.startsWith('image/')
        ? URL.createObjectURL(file)
        : undefined;
      return { file, preview };
    });
    setFiles(prev => [...prev, ...filePreviews]);
  };

  const removeFile = (index: number) => {
    setFiles(prev => {
      const file = prev[index];
      if (file.preview) URL.revokeObjectURL(file.preview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items);
    const imageFiles = items
      .filter(item => item.type.startsWith('image/'))
      .map(item => item.getAsFile())
      .filter((file): file is File => file !== null);

    if (imageFiles.length > 0) {
      addFiles(imageFiles);
    }
  };

  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) {
      return <ImageIcon size={16} />;
    }
    return <FileText size={16} />;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="chat-area__input-section">
      <div
        className={`input-area ${isDragging ? 'input-area--dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* File previews */}
        {files.length > 0 && (
          <div className="input-area__files">
            {files.map((filePreview, index) => (
              <div key={index} className="file-chip">
                <div className="file-chip__preview">
                  {filePreview.preview ? (
                    <img src={filePreview.preview} alt={filePreview.file.name} />
                  ) : (
                    getFileIcon(filePreview.file.type)
                  )}
                </div>
                <div className="file-chip__info">
                  <div className="file-chip__name">{filePreview.file.name}</div>
                  <div className="file-chip__size">{formatFileSize(filePreview.file.size)}</div>
                </div>
                <button
                  className="file-chip__remove"
                  onClick={() => removeFile(index)}
                  title="Remove file"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="input-area__wrapper">
          <button
            className="input-area__attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming || !currentChatId}
            title="Attach files"
          >
            <Paperclip size={18} />
          </button>

          <textarea
            ref={textareaRef}
            className="input-area__textarea"
            placeholder={files.length > 0
              ? "Add a message (optional)..."
              : "Type your message... (Shift+Enter for new line)"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            disabled={isStreaming || !currentChatId}
            rows={1}
          />

          <button
            className="input-area__send-btn"
            onClick={handleSend}
            disabled={(!input.trim() && files.length === 0) || isStreaming || !currentChatId}
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.txt,.md,.csv,.json,.xml,.html,.css,.js,.ts,.tsx,.jsx,.py,.java,.c,.cpp,.h,.hpp"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {isDragging && (
          <div className="input-area__drop-overlay">
            <div className="input-area__drop-text">Drop files here</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default InputArea;
