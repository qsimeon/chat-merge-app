import logging
from typing import AsyncGenerator, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MergeHistory
from app.providers.factory import create_provider
from app.providers.base import StreamChunk
from app.services.chat_service import get_chat, get_messages, create_chat, create_message
from app.services.completion_service import get_api_key, _get_rag_keys
from app.services import vector_service
from app.schemas import ChatCreate

logger = logging.getLogger(__name__)

# Prompt to generate a brief intro message for the new merged chat
MERGED_INTRO_PROMPT = """You are the assistant inside a newly merged AI chat. Two separate conversations have been intelligently combined into a single semantic memory that you can search.

Below are brief excerpts from the two conversations. Write a SHORT (2-4 sentence) intro message that:
1. States which conversations were merged and their main topics
2. Tells the user they can ask anything from either conversation
3. Is warm and direct — no fluff

## Conversation 1: "{title_1}"
{convo_1_summary}

## Conversation 2: "{title_2}"
{convo_2_summary}

Write ONLY the brief intro message (no labels, no prefix, just the text):"""


def _summarize_conversation(messages, max_messages: int = 6) -> str:
    """Create a brief text summary of a conversation for the intro prompt."""
    lines = []
    subset = messages[:3] + messages[-3:] if len(messages) > max_messages else messages
    for msg in subset:
        if msg.role == "system":
            continue
        role_label = "User" if msg.role == "user" else "Assistant"
        content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines) if lines else "(no messages)"


async def merge_chats(
    db: AsyncSession,
    chat_ids: List[str],
    merge_provider: str,
    merge_model: str,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Merge multiple chats via vector fusion.

    How it works:
    1. Load source chats (message samples for AI intro only — NOT copying messages)
    2. Create an EMPTY merged chat (zero copied messages in DB)
    3. Fuse vector namespaces intelligently (nearest-neighbor + averaging)
       — falls back to simple union if fusion fails, with a warning emitted
    4. Generate brief AI intro message describing what was merged
    5. RAG is the SOLE context mechanism for all future queries in this chat

    The merged chat scales to conversations of any length (no context window explosion).
    """
    try:
        # Step 1: Load source chats and sample messages for AI intro
        yield StreamChunk(type="content", data="Loading conversations...\n")

        chats_data = []
        for i, chat_id in enumerate(chat_ids):
            chat = await get_chat(db, chat_id)
            if not chat:
                yield StreamChunk(type="error", data=f"Chat {chat_id} not found")
                return
            messages = await get_messages(db, chat_id)
            chats_data.append((chat, messages))

        chat_titles = [chat.title or f"Chat {i+1}" for i, (chat, _) in enumerate(chats_data)]
        total_messages = sum(len(msgs) for _, msgs in chats_data)

        yield StreamChunk(
            type="content",
            data=f"Found {len(chats_data)} conversations with {total_messages} total messages.\n"
        )

        # Step 2: Create empty merged chat (no messages copied — RAG is sole context)
        merge_title = "Merged: " + ", ".join(chat_titles)
        merge_system_prompt = (
            f"You are a merged AI assistant with access to semantically fused context "
            f"from {len(chats_data)} conversations: {', '.join(chat_titles)}. "
            "Use retrieved context to answer queries. "
            "The user may ask about topics from any of the merged conversations."
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

        # Mark as merged so completion_service always uses RAG
        merged_chat.is_merged = True
        db.add(merged_chat)
        await db.flush()

        yield StreamChunk(type="content", data="Created merged chat (empty — context via RAG).\n")

        # Step 3: Fuse vector namespaces (the main work)
        pinecone_key, openai_key = await _get_rag_keys(db)
        fusion_warning = None

        if not pinecone_key:
            yield StreamChunk(
                type="error",
                data="Pinecone key is required for merged chats. Add your Pinecone key in Settings."
            )
            # Roll back the chat we just created
            await db.rollback()
            return

        yield StreamChunk(type="content", data="Fusing vector stores (smart merge)...\n")
        try:
            fusion_result = await vector_service.fuse_namespaces(
                source_chat_ids=chat_ids,
                target_chat_id=merged_chat.id,
                pinecone_key=pinecone_key,
                threshold=0.82,
            )
            fused = fusion_result["fused"]
            kept = fusion_result["kept"]
            total = fusion_result["total"]
            yield StreamChunk(
                type="content",
                data=f"Vector fusion complete: {fused} pairs fused, {kept} unique kept → {total} total vectors.\n"
            )
        except Exception as e:
            logger.error(f"ERROR: Smart fusion failed — fell back to simple union merge. Reason: {e}")
            fusion_warning = f"Smart fusion failed — using simple union merge. Reason: {e}"
            yield StreamChunk(type="warning", data=fusion_warning)
            try:
                await vector_service.merge_vector_namespaces(
                    source_chat_ids=chat_ids,
                    target_chat_id=merged_chat.id,
                    pinecone_key=pinecone_key,
                    openai_key=openai_key,
                )
                yield StreamChunk(type="content", data="Fallback union merge complete.\n")
            except Exception as e2:
                logger.error(f"Fallback union merge also failed: {e2}")
                yield StreamChunk(type="content", data=f"Vector merge failed: {e2}\n")

        # Step 4: Generate AI intro message
        yield StreamChunk(type="content", data="Generating intro message...\n")

        api_key = await get_api_key(db, merge_provider)
        intro_content = None

        if api_key:
            try:
                provider = create_provider(merge_provider, api_key)
                convo_summaries = [_summarize_conversation(msgs) for _, msgs in chats_data]

                intro_prompt = MERGED_INTRO_PROMPT.format(
                    title_1=chat_titles[0],
                    convo_1_summary=convo_summaries[0],
                    title_2=chat_titles[1] if len(chat_titles) > 1 else "Other conversations",
                    convo_2_summary=convo_summaries[1] if len(convo_summaries) > 1 else "(none)",
                )

                intro_text = ""
                async for chunk in provider.stream_completion(
                    messages=[{"role": "user", "content": intro_prompt}],
                    model=merge_model,
                    max_tokens=300,
                ):
                    if chunk.type == "content":
                        intro_text += chunk.data

                if intro_text.strip():
                    intro_content = intro_text.strip()
                    if fusion_warning:
                        intro_content += f"\n\n⚠ {fusion_warning}"

            except Exception as e:
                logger.warning(f"Failed to generate intro message: {e}")

        # Fallback intro if AI generation failed
        if not intro_content:
            intro_content = (
                f"I've merged **{', '.join(chat_titles)}** into a unified semantic memory. "
                "Ask me anything that was covered in either conversation — I'll retrieve the most relevant context automatically."
            )
            if fusion_warning:
                intro_content += f"\n\n⚠ {fusion_warning}"

        await create_message(db, merged_chat.id, "assistant", intro_content)
        yield StreamChunk(type="content", data=f"\n{intro_content}\n")

        # Step 5: Save merge history
        merge_history = MergeHistory(
            source_chat_ids=chat_ids,
            merged_chat_id=merged_chat.id,
            merge_model=merge_model,
        )
        db.add(merge_history)
        await db.commit()

        logger.info(f"Vector-fusion merge complete: {chat_ids} → {merged_chat.id}")

        yield StreamChunk(type="content", data="\nMerge complete!\n")
        yield StreamChunk(type="merge_complete", data=merged_chat.id)

    except Exception as e:
        logger.error(f"Merge error: {str(e)}")
        yield StreamChunk(type="error", data=f"Merge failed: {str(e)}")
