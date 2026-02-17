import logging
import shutil
from pathlib import Path
from typing import AsyncGenerator, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models import MergeHistory, Attachment
from app.providers.factory import create_provider
from app.providers.base import StreamChunk
from app.services.chat_service import get_chat, get_messages, create_chat, create_message
from app.services.completion_service import get_api_key
from app.services import vector_service
from app.schemas import ChatCreate

logger = logging.getLogger(__name__)

# Brief prompt — only used to generate a short bridging message, NOT to rewrite conversations
SYNTHESIS_INTRO_PROMPT = """You are helping merge two AI conversations into one unified thread. The user wants to continue a single conversation that has the full context of both.

Below are brief excerpts from the two conversations being merged. Your job is to write a BRIEF (2-4 sentence) bridging message from the assistant's perspective that:
1. Acknowledges the key topics from both conversations
2. Connects them naturally
3. Invites the user to continue

Do NOT rewrite or summarize the conversations in detail. Just write the bridging message.
Keep it concise — this is just a transition.

## Conversation 1: "{title_1}"
{convo_1_summary}

## Conversation 2: "{title_2}"
{convo_2_summary}

Write ONLY the brief bridging assistant message (no labels, no prefix, just the text):"""


def _summarize_conversation(messages, max_messages: int = 6) -> str:
    """Create a brief summary of a conversation for the synthesis intro prompt."""
    lines = []
    subset = messages[:3] + messages[-3:] if len(messages) > max_messages else messages
    for msg in subset:
        if msg.role == "system":
            continue
        role_label = "User" if msg.role == "user" else "Assistant"
        content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


async def merge_chats(
    db: AsyncSession,
    chat_ids: List[str],
    merge_provider: str,
    merge_model: str,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Merge multiple chats by combining their FULL message histories.

    How it works:
    1. Load all messages from all source chats
    2. Create a new chat and copy every single message into it (chronologically)
    3. Include reasoning traces so the full thinking context is preserved
    4. Generate a brief AI synthesis bridge at the end
    5. When the user continues chatting, the model sees ALL messages from all source chats

    This is NOT a summary/rewrite — it's a true context merge.
    """
    try:
        # Step 1: Load all chats and their messages
        yield StreamChunk(type="content", data="Loading conversations...\n")

        chats_data = []
        all_messages_with_source = []

        for i, chat_id in enumerate(chat_ids):
            chat = await get_chat(db, chat_id)
            if not chat:
                yield StreamChunk(type="error", data=f"Chat {chat_id} not found")
                return

            messages = await get_messages(db, chat_id)
            chats_data.append((chat, messages))

            for msg in messages:
                all_messages_with_source.append((msg, chat.title or f"Chat {i+1}", i))

        chat_titles = [chat.title or f"Chat {i+1}" for i, (chat, _) in enumerate(chats_data)]
        total_messages = sum(len(msgs) for _, msgs in chats_data)

        yield StreamChunk(
            type="content",
            data=f"Found {len(chats_data)} conversations with {total_messages} total messages.\n"
        )

        # Step 2: Create the merged chat
        merge_title = "Merged: " + ", ".join(chat_titles)

        merge_system_prompt = (
            f"This conversation was created by merging {len(chats_data)} separate conversations: "
            f"{', '.join(chat_titles)}. "
            "The full message history from all source conversations is included in the chat history. "
            "Continue the conversation naturally, drawing on the full context from all merged threads. "
            "The user may reference topics from any of the merged conversations."
        )

        merged_chat = await create_chat(
            db,
            ChatCreate(
                title=merge_title,
                provider=merge_provider,
                model=merge_model,
                system_prompt=merge_system_prompt,
            )
        )

        yield StreamChunk(type="content", data=f"Created merged chat.\n")

        # Step 3: Copy ALL messages chronologically
        yield StreamChunk(type="content", data="Copying full message histories with reasoning traces...\n")

        # Sort all messages by timestamp
        all_messages_with_source.sort(
            key=lambda x: x[0].created_at or datetime.min
        )

        copied = 0
        current_source = -1

        for msg, source_title, source_idx in all_messages_with_source:
            # Add context markers when switching between source conversations
            if source_idx != current_source:
                current_source = source_idx
                await create_message(
                    db, merged_chat.id, "system",
                    f"--- Context from: {source_title} ---",
                )

            # Copy the message with its full reasoning trace
            new_message = await create_message(
                db, merged_chat.id,
                msg.role,
                msg.content,
                reasoning_trace=msg.reasoning_trace,
            )

            # Copy attachments if the message has any
            if msg.attachments and new_message:
                for att in msg.attachments:
                    # Copy file to new location
                    source_path = Path(att.storage_path)
                    if source_path.exists():
                        # Create new filename to avoid collisions
                        from uuid import uuid4
                        new_filename = f"{uuid4()}{source_path.suffix}"
                        new_path = source_path.parent / new_filename

                        # Copy file
                        shutil.copy2(source_path, new_path)

                        # Create new attachment record
                        new_attachment = Attachment(
                            message_id=new_message.id,
                            file_name=att.file_name,
                            file_type=att.file_type,
                            file_size=att.file_size,
                            storage_path=str(new_path)
                        )
                        db.add(new_attachment)

            copied += 1

        yield StreamChunk(
            type="content",
            data=f"Copied {copied} messages (including reasoning traces) into merged chat.\n"
        )

        # Step 4: Generate brief synthesis bridge
        yield StreamChunk(type="content", data="Generating synthesis bridge...\n")

        api_key = await get_api_key(db, merge_provider)
        synthesis_content = None

        if api_key:
            try:
                provider = create_provider(merge_provider, api_key)

                convo_summaries = [
                    _summarize_conversation(msgs)
                    for _, msgs in chats_data
                ]

                # Build prompt for just the first two conversations
                synthesis_prompt = SYNTHESIS_INTRO_PROMPT.format(
                    title_1=chat_titles[0],
                    convo_1_summary=convo_summaries[0],
                    title_2=chat_titles[1] if len(chat_titles) > 1 else "Other conversations",
                    convo_2_summary=convo_summaries[1] if len(convo_summaries) > 1 else "\n".join(convo_summaries[1:]),
                )

                synthesis_text = ""
                synthesis_reasoning = ""

                async for chunk in provider.stream_completion(
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    model=merge_model,
                    max_tokens=500,
                ):
                    if chunk.type == "content":
                        synthesis_text += chunk.data
                    elif chunk.type == "reasoning":
                        synthesis_reasoning += chunk.data

                if synthesis_text.strip():
                    synthesis_content = synthesis_text.strip()
                    await create_message(
                        db, merged_chat.id, "assistant",
                        synthesis_content,
                        reasoning_trace=synthesis_reasoning if synthesis_reasoning else None,
                    )

            except Exception as e:
                logger.warning(f"Failed to generate synthesis intro: {e}")

        # Fallback if AI synthesis failed
        if not synthesis_content:
            synthesis_content = (
                f"I now have the full context from both conversations: {', '.join(chat_titles)}. "
                "All messages and reasoning traces have been merged. How would you like to continue?"
            )
            await create_message(db, merged_chat.id, "assistant", synthesis_content)

        yield StreamChunk(type="content", data=f"\n{synthesis_content}\n")

        # Step 5: Merge vector namespaces for RAG retrieval
        yield StreamChunk(type="content", data="Merging vector stores for RAG retrieval...\n")
        try:
            rag_success = await vector_service.merge_vector_namespaces(
                source_chat_ids=chat_ids,
                target_chat_id=merged_chat.id
            )
            if rag_success:
                yield StreamChunk(type="content", data="Vector stores merged.\n")
            else:
                yield StreamChunk(type="content", data="Vector store merge partial (RAG will fall back to recent messages).\n")
        except Exception as e:
            logger.warning(f"Vector merge failed (non-fatal): {e}")
            yield StreamChunk(type="content", data="Note: RAG vector merge unavailable (Pinecone not configured).\n")

        # Step 6: Save merge history
        merge_history = MergeHistory(
            source_chat_ids=chat_ids,
            merged_chat_id=merged_chat.id,
            merge_model=merge_model,
        )
        db.add(merge_history)
        await db.commit()

        logger.info(f"Full-context merge: {chat_ids} -> {merged_chat.id} ({copied} messages)")

        yield StreamChunk(type="content", data="\nMerge complete!\n")
        yield StreamChunk(type="merge_complete", data=merged_chat.id)

    except Exception as e:
        logger.error(f"Merge error: {str(e)}")
        yield StreamChunk(type="error", data=f"Merge failed: {str(e)}")
