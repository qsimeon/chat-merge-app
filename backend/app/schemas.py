from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Chat schemas
class ChatCreate(BaseModel):
    """Create a new chat"""
    title: Optional[str] = None
    provider: str = Field(..., description="Provider: openai, anthropic, or gemini")
    model: str = Field(..., description="Model name from the provider")
    system_prompt: Optional[str] = None


class AttachmentResponse(BaseModel):
    """Attachment response"""
    id: str
    message_id: str
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    created_at: Optional[str] = None


class MessageResponse(BaseModel):
    """Message response"""
    id: str
    chat_id: str
    role: str
    content: str
    reasoning_trace: Optional[str] = None
    created_at: Optional[str] = None
    attachments: List[AttachmentResponse] = []


class ChatResponse(BaseModel):
    """Chat response with all details"""
    id: str
    title: Optional[str] = None
    provider: str
    model: str
    system_prompt: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int
    messages: List[MessageResponse] = []


class ChatListItem(BaseModel):
    """Chat item in list"""
    id: str
    title: Optional[str] = None
    provider: str
    model: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int


# Message schemas
class MessageCreate(BaseModel):
    """Create a new message"""
    role: str = Field(..., description="user or assistant")
    content: str
    reasoning_trace: Optional[str] = None


class CompletionRequest(BaseModel):
    """Request for chat completion"""
    content: str = Field(..., description="User message content")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature")
    max_tokens: Optional[int] = None
    attachment_ids: Optional[List[str]] = Field(None, description="List of attachment IDs to include")


# API Key schemas
class APIKeyCreate(BaseModel):
    """Create/update API key"""
    provider: str = Field(..., description="openai, anthropic, or gemini")
    api_key: str = Field(..., description="The actual API key")


class APIKeyResponse(BaseModel):
    """API key response (never includes the key itself)"""
    id: str
    provider: str
    is_active: bool
    created_at: Optional[str] = None


# Merge schemas
class MergeRequest(BaseModel):
    """Request to merge multiple chats"""
    chat_ids: List[str] = Field(..., min_items=2, description="At least 2 chat IDs")
    merge_provider: str = Field(..., description="Provider for merge model")
    merge_model: str = Field(..., description="Model to use for merging")


class MergeResponse(BaseModel):
    """Response from merge operation"""
    merged_chat_id: str
    source_chat_ids: List[str]
    merge_model: str


# Stream schemas
class StreamChunk(BaseModel):
    """Chunk of streaming response"""
    type: str = Field(..., description="content, reasoning, error, or done")
    data: str


# Models endpoint
class ModelsResponse(BaseModel):
    """Available models per provider"""
    openai: List[str]
    anthropic: List[str]
    gemini: List[str]
