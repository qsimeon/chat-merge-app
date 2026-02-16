# ChatMerge Frontend

A modern React + TypeScript frontend for a multi-provider AI chat application with intelligent conversation merging capabilities.

## Features

- **Multi-Provider Support**: Seamlessly switch between OpenAI, Anthropic, and Google Gemini
- **Intelligent Merge**: Combine multiple conversations using AI to create cohesive merged chats
- **Real-time Streaming**: See responses stream in real-time with reasoning traces
- **API Key Management**: Securely manage API keys for different providers
- **Modern UI**: Clean, dark-themed interface inspired by ChatGPT/Claude
- **State Management**: Zustand for efficient state management
- **TypeScript**: Full type safety across the application

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── App.tsx                 # Main app component
│   │   ├── Sidebar.tsx             # Chat list and navigation
│   │   ├── ChatArea.tsx            # Main chat display area
│   │   ├── MessageBubble.tsx       # Individual message rendering
│   │   ├── InputArea.tsx           # Message input component
│   │   ├── SettingsModal.tsx       # API key management
│   │   └── MergeModal.tsx          # Chat merge interface
│   ├── api.ts                      # API client with streaming support
│   ├── store.ts                    # Zustand state management
│   ├── types.ts                    # TypeScript interfaces
│   ├── index.css                   # Global styles (plain CSS, no Tailwind)
│   └── main.tsx                    # React entry point
├── index.html                      # HTML entry point
├── vite.config.ts                  # Vite configuration
├── tsconfig.json                   # TypeScript configuration
└── package.json                    # Dependencies

```

## Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Configuration

The frontend is configured to proxy API requests to `http://localhost:8000` (the backend server).

Update `vite.config.ts` if your backend runs on a different port:

```typescript
proxy: {
  '/api': {
    target: 'http://your-backend:port',
    changeOrigin: true,
  }
}
```

## Key Components

### Sidebar
- List of all chats with provider and model information
- Create new chats with provider/model selection
- Delete chats
- Merge chats button (appears when 2+ chats exist)
- Settings button for API key management

### Chat Area
- Display messages with proper formatting
- Show streaming responses with typing animation
- Collapsible reasoning traces for models that provide them
- Edit chat titles inline
- Auto-scroll to latest messages

### Message Rendering
- Markdown-like formatting support:
  - Code blocks with ` ``` ... ``` `
  - Inline code with backticks
  - Bold text with `**...**`
  - Line breaks preserved
- Syntax highlighting ready structure

### Merge Modal
- Select multiple chats to merge
- Choose provider and model for merge operation
- Real-time progress display
- Auto-navigate to merged chat on completion

### Settings Modal
- Add/delete API keys for each provider
- Show/hide password for API keys
- Real-time validation

## API Integration

The frontend communicates with the backend using:

- **REST API**: For standard CRUD operations
- **Server-Sent Events (SSE)**: For streaming responses

### Streaming Implementation

The `api.ts` file includes a custom streaming handler using fetch with `ReadableStream`:

```typescript
async function* streamFetch(url: string, body: Record<string, unknown>): AsyncGenerator<StreamChunk>
```

This properly parses SSE format responses line by line.

## Styling

All styles are in plain CSS (no Tailwind) in `/src/index.css`:

- **Color Scheme**: Dark theme with purple accents
- **Responsive**: Sidebar collapses on mobile
- **Smooth Animations**: Fade-ins, slide-ups, and typing animations
- **Custom Scrollbars**: Styled to match theme

### CSS Variables

Define the theme with CSS custom properties:

```css
--bg-primary: #1a1a2e
--accent: #7c3aed
--text-primary: #ffffff
... etc
```

## State Management

Zustand store handles:

- Chat list and selection
- Messages for current chat
- Streaming state and content
- API keys
- Modal visibility
- Merge operation state

Access store with:

```typescript
import { useStore } from '../store';

const { chats, currentMessages, sendMessage } = useStore();
```

## TypeScript Types

Key interfaces in `types.ts`:

```typescript
interface Chat { ... }
interface Message { ... }
interface APIKeyInfo { ... }
interface MergeRequest { ... }
interface StreamChunk { ... }
```

## Development Tips

1. **Local Testing**: Run `npm run dev` and backend on `localhost:8000`
2. **TypeScript Checking**: Type errors will appear in the console
3. **Hot Module Replacement**: Changes auto-reload with Vite
4. **Inspector**: Use React DevTools to inspect component state

## Browser Support

- Chrome/Edge: Latest versions
- Firefox: Latest versions
- Safari: Latest versions
- Requires ES2020+ support

## Troubleshooting

**API calls failing**: Check that backend is running on `localhost:8000` and CORS is configured.

**Streaming not working**: Verify backend is sending SSE format with `data: {...}\n\n`.

**Styles not loading**: Clear browser cache or check CSS file exists.

**TypeScript errors**: Ensure all types are properly imported from `types.ts`.

## Future Enhancements

- Export conversations to Markdown/PDF
- Conversation search and filtering
- Custom system prompts per chat
- Token usage tracking
- Chat history with timestamps
- Multi-user support
- Voice input/output
