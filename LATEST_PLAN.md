# Plan: Proper Vector-Fusion-Based Chat Merge

## Diagnosis: Current State vs. Vision

### What we're doing (wrong)
1. **Merge copies every message** into the merged chat's DB — literal O(n) text concatenation
2. **Vectors are simply unioned** — merged namespace = A ∪ B, no intelligence
3. **No merged-chat detection** — merged chats only get RAG because they happen to have >10 messages
4. **Screenshot confirms** the UI showing "--- Context from: Convo 2 ---" separator rows — proof that raw messages are being dumped in

### What the vision requires
- Merged chat has **zero copied messages** in DB
- Vector stores are **intelligently fused** (nearest-neighbor + average), not just concatenated
- RAG is the **sole context mechanism** for merged chats — not a fallback for when messages get long
- The merged namespace is a **compressed semantic representation** of both conversations, smaller than their union
- Scales to conversations of any length (no context window explosion)

---

## Architecture: The Correct Approach

### Per-chat vector store (unchanged, already correct)
Every message sent to any chat → embed → upsert into that chat's Pinecone namespace.
Each chat = its own isolated namespace.

### Smart Merge = Vector Fusion + Empty DB Chat

**Step A — Hybrid-fuse vector namespaces** (the innovation):

The result is a **hybrid between a union and a fusion** — larger than the bigger source but smaller than the sum of both. Semantically redundant content gets merged; genuinely unique content from each chat is preserved.

```
source_A: 100 vectors (Chat A)
source_B:  80 vectors (Chat B)

Algorithm:
  working_set = all 100 vectors from A
  for each vector w in B:
    nn = nearest neighbor in working_set (cosine similarity)
    if cosine(w, nn) >= threshold (0.82):
      # semantically overlapping — fuse into one
      replace nn with normalize((nn + w) / 2)    # averaged embedding
      metadata = "[A]: {content_A}\n[B]: {content_B}", type="fused"
    else:
      # unique concept from B — keep both
      append w to working_set                     # union for unique content

# Result size: anywhere from 100 to 180, depending on overlap
# If half of B overlaps with A → ~140 vectors (in the middle)
merged_namespace = working_set
```

**Why this is the right target size**: the user said "somewhere in the middle of the larger and the sum of the two." This happens naturally — the threshold controls where in that range we land (lower threshold = more fusions = smaller; higher = more unions = larger). Default 0.82 aims for ~middle.

**Step B — Create empty merged chat**:
- `merged_chat` in DB has 0 user/assistant messages
- System prompt: "You are a merged AI assistant with access to semantically fused context from two conversations: [titles]. Use retrieved context to answer queries."
- One initial assistant message: brief AI-generated summary of what was merged (topics covered)

**Step C — RAG for every query in merged chat**:
- No concept of "short vs. long conversation" for merged chats
- Every user message → embed → query fused namespace → get top-K → inject as context
- Format: structured context block, not inline conversation history

---

## Files to Change

### 1. `backend/app/services/vector_service.py`
Add `fuse_namespaces(source_ids, target_id, pinecone_key, openai_key, threshold=0.82)`:
- Fetch all vectors from each source via `index.list()` + `index.fetch()` (already working)
- **Compute cosine similarity locally** with numpy (no extra API calls)
  ```python
  import numpy as np
  def _cosine(a, b): return np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b)+1e-8)
  ```
- Pairwise nearest-neighbor fusion algorithm (see above)
- Fused vector metadata: `{type:"fused", content:"[A]: ...\n[B]: ...", source_a_id, source_b_id, source_a_chat, source_b_chat}`
- Kept vector metadata: `{type:"kept", source_chat_id, original_message_id, ...original metadata}`
- Upsert all into target namespace

Keep existing `merge_vector_namespaces` (simple union) as an internal fallback only.

### 2. `backend/app/services/merge_service.py`
**Remove Step 3 entirely** (message copying loop, all `create_message()` calls for source messages).
**Remove attachment copying.**

New flow:
1. Load chat titles + sample messages for AI summary (first 3 + last 3 from each)
2. Create empty merged chat with system prompt
3. Call `vector_service.fuse_namespaces()` — this is the main work
4. Generate brief AI intro message: "I've merged [Chat A] and [Chat B]. Topics covered: [summary]. Ask me anything from either conversation."
5. Save intro as first assistant message
6. Record MergeHistory

### 3. `backend/app/models.py`
Add `is_merged = Column(Boolean, default=False)` to `Chat` model.
Set to `True` in `merge_service.py` when creating merged chat.
(Avoids querying MergeHistory table on every completion.)

### 4. `backend/app/schemas.py`
Add `is_merged: bool = False` to `ChatResponse` schema.

### 5. `backend/app/services/completion_service.py`
Add merged-chat detection:
```python
is_merged = chat.is_merged  # new field
```

For merged chats, **always** use RAG regardless of message count, and format context differently:
```python
async def _build_merged_chat_context(db, chat, user_query, pinecone_key, openai_key):
    # Query fused namespace
    hits = await vector_service.query_relevant_context(
        chat_id=chat.id, query_text=user_query,
        pinecone_key=pinecone_key, openai_key=openai_key, top_k=8
    )
    # Build context block from hits (fused or kept vectors)
    context_block = _format_rag_context_block(hits)
    # Get recent messages from merged chat itself (user's new messages since merge)
    recent = await get_messages(db, chat.id)
    # Return: context injection + recent history
```

The context injection is added as a special system-level message just before the user's new message:
```
[Retrieved context from merged conversations — most relevant to your query]
---
{content from hit 1}
...
---
```

For regular chats: unchanged behavior.

### 6. `backend/app/routes/chats.py`
Include `is_merged` in chat list and get responses so frontend can show the RAG badge.

### 7. Frontend — minimal changes
- In `types.ts`: add `is_merged?: boolean` to `Chat` interface
- In `ChatArea.tsx`: show a "RAG-powered" badge in header when `chat.is_merged`
- In `MergeModal.tsx`: update status messages to reflect the new approach

---

## Fallback Policy
Pinecone key is a **hard requirement** of this app — just like LLM provider keys. No code paths that work without it.

The only fallback is **technical failure of the fusion algorithm itself** (Pinecone API error, numpy exception, etc.):
- Fall back to simple union (just copy both namespaces verbatim)
- Log clearly: `ERROR: Smart fusion failed — fell back to simple union merge. Reason: {e}`
- Surface to the user in the UI: a yellow/orange warning banner in the merged chat header: "⚠ Smart fusion failed — using simple union merge. See logs for details."
- The `StreamChunk` returned during merge should emit a `type="warning"` event with this message so the frontend can display it

No other fallbacks. If Pinecone key is missing, merging should fail with a clear error (same as missing LLM key).

---

## numpy dependency
`numpy` is likely already installed in the conda env. Add to `backend/requirements.txt` if not present.

---

## Verification
1. Run `python -c "from main import app; print('OK')"` — import check
2. Create two chats, send 5+ messages each → verify vectors stored (check logs)
3. Merge them → verify:
   - Merged chat has 0 copied messages (only the AI intro)
   - Server logs show "Fused X pairs, kept Y unique"
   - Merged Pinecone namespace vector count ≈ max(|A|,|B|) to |A|+|B|
4. Ask a question in merged chat that relates to Chat A's content → verify server logs show RAG retrieved from correct source
5. Ask a question relating to Chat B's content → verify different context retrieved

---

## What Changes at the User Level
**Before**: Merge = new chat pre-loaded with all old messages (context window bomb)
**After**: Merge = new empty chat backed by a fused semantic memory; scales infinitely
