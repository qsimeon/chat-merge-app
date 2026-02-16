from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from app.database import Base


class Chat(Base):
    """Chat conversation model"""
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    title = Column(String, nullable=True)
    provider = Column(String, nullable=False)  # "openai", "anthropic", "gemini"
    model = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def to_dict(self, include_messages=False):
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "title": self.title,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }
        if include_messages:
            data["messages"] = [msg.to_dict() for msg in self.messages]
        return data


class Message(Base):
    """Chat message model"""
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    chat_id = Column(
        String,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False
    )
    role = Column(String, nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    reasoning_trace = Column(Text, nullable=True)  # For extended thinking/CoT
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    attachments = relationship(
        "Attachment",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "role": self.role,
            "content": self.content,
            "reasoning_trace": self.reasoning_trace,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "attachments": [att.to_dict() for att in self.attachments] if self.attachments else [],
        }


class APIKey(Base):
    """Stored API keys (encrypted)"""
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    provider = Column(String, nullable=False, unique=True)  # "openai", "anthropic", "gemini"
    encrypted_key = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary (never include the actual key)"""
        return {
            "id": self.id,
            "provider": self.provider,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Attachment(Base):
    """File/image attachments for messages"""
    __tablename__ = "attachments"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    message_id = Column(
        String,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False
    )
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # MIME type
    file_size = Column(Integer, nullable=False)  # bytes
    storage_path = Column(Text, nullable=False)  # local path or cloud URL
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="attachments")

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MergeHistory(Base):
    """Track merge operations"""
    __tablename__ = "merge_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    source_chat_ids = Column(JSON, nullable=False)  # list of chat IDs
    merged_chat_id = Column(String, ForeignKey("chats.id"), nullable=False)
    merge_model = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "source_chat_ids": self.source_chat_ids,
            "merged_chat_id": self.merged_chat_id,
            "merge_model": self.merge_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
