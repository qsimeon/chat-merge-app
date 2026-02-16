import { useState } from 'react';
import { Message } from '../types';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
}

function formatContent(content: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // Split by code blocks (``` ... ```)
  const codeBlockRegex = /```([\s\S]*?)```/g;
  let match;
  const matches: Array<{ index: number; length: number; content: string }> = [];

  while ((match = codeBlockRegex.exec(content)) !== null) {
    matches.push({
      index: match.index,
      length: match[0].length,
      content: match[1],
    });
  }

  // Process content with code blocks
  matches.forEach((codeBlock) => {
    // Add text before code block
    if (codeBlock.index > lastIndex) {
      const textBefore = content.substring(lastIndex, codeBlock.index);
      parts.push(formatInlineContent(textBefore));
    }

    // Add code block
    parts.push(
      <pre key={`code-${codeBlock.index}`}>
        <code>{codeBlock.content.trim()}</code>
      </pre>
    );

    lastIndex = codeBlock.index + codeBlock.length;
  });

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(formatInlineContent(content.substring(lastIndex)));
  }

  return parts.length > 0 ? parts : [formatInlineContent(content)];
}

function formatInlineContent(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // Replace inline code
  const inlineCodeRegex = /`([^`]+)`/g;
  let match;

  while ((match = inlineCodeRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    parts.push(
      <code key={`inline-${match.index}`}>{match[1]}</code>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  const content = parts.length > 0 ? parts : text;

  // Split by newlines and handle bold text
  return (
    <>
      {Array.isArray(content)
        ? content.map((part, idx) => {
            if (typeof part === 'string') {
              const segments = part.split(/(\*\*[^*]+\*\*|\n)/);
              return segments.map((seg, i) => {
                if (seg === '\n') return <br key={`br-${idx}-${i}`} />;
                if (seg.startsWith('**') && seg.endsWith('**')) {
                  return (
                    <strong key={`bold-${idx}-${i}`}>
                      {seg.slice(2, -2)}
                    </strong>
                  );
                }
                return <span key={`text-${idx}-${i}`}>{seg}</span>;
              });
            }
            return part;
          })
        : content}
    </>
  );
}

function MessageBubble({ message }: MessageBubbleProps) {
  const [showReasoning, setShowReasoning] = useState(false);

  return (
    <div className={`message message--${message.role}`}>
      <div className="message__content">
        {formatContent(message.content)}

        {message.reasoning_trace && (
          <>
            <button
              className="message__reasoning-toggle"
              onClick={() => setShowReasoning(!showReasoning)}
            >
              {showReasoning ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              {showReasoning ? 'Hide' : 'Show'} reasoning
            </button>

            {showReasoning && (
              <div className="message__reasoning">
                {formatContent(message.reasoning_trace)}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;
