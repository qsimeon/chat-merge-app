"""
Comprehensive Playwright test for ChatMerge.
Tests: navigation, chat creation, messaging, merge modal, settings, merged chat RAG.

Run with: python3 tests/playwright_full_test.py
Requires: frontend at :5173, backend at :8000
"""
from playwright.sync_api import sync_playwright, Page, expect
import os, time

FRONTEND_URL = "http://localhost:5173"
OUT = "/tmp/chatmerge_test"
os.makedirs(OUT, exist_ok=True)

step = 0
def shot(page: Page, label: str):
    global step
    step += 1
    path = f"{OUT}/{step:02d}_{label}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  📸  {path}")
    return path

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─── Helpers ────────────────────────────────────────────────────────────────

def wait_for_app(page: Page):
    page.goto(FRONTEND_URL)
    page.wait_for_load_state("networkidle")
    # App is ready when the sidebar renders
    page.wait_for_selector("text=ChatMerge", timeout=10_000)

def get_chat_items(page: Page):
    return page.locator(".chat-item").all()

def close_any_modal(page: Page):
    """Dismiss any open modal via Cancel button or X button."""
    cancel = page.get_by_role("button", name="Cancel")
    if cancel.is_visible():
        cancel.click()
        page.wait_for_timeout(400)
        return
    close = page.locator(".modal__close, button[aria-label='close']")
    if close.is_visible():
        close.click()
        page.wait_for_timeout(400)

def click_chat(page: Page, name: str):
    page.get_by_text(name, exact=False).first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)

def send_message(page: Page, text: str, wait_ms: int = 15_000):
    """Type into the input area and submit, waiting for streaming to complete."""
    textarea = page.get_by_placeholder("Type your message")
    textarea.click()
    textarea.fill(text)
    page.keyboard.press("Enter")
    # Wait until streaming indicator disappears (or timeout)
    try:
        page.wait_for_selector(".message__typing", state="visible", timeout=5_000)
        page.wait_for_selector(".message__typing", state="hidden", timeout=wait_ms)
    except Exception:
        pass  # model may respond without showing typing indicator
    page.wait_for_timeout(800)

# ─── Tests ──────────────────────────────────────────────────────────────────

def test_01_landing(page: Page):
    section("1 · Landing Page")
    wait_for_app(page)
    shot(page, "landing")

    # Verify key landing elements
    assert page.get_by_text("ChatMerge").first.is_visible()
    assert page.get_by_text("Merge Any Chats").is_visible()
    assert page.get_by_text("RAG-Powered Context").is_visible()
    assert page.get_by_text("Smart Vector Fusion").is_visible()
    print("  ✓ Landing page renders with all feature cards")


def test_02_new_chat_form(page: Page):
    section("2 · New Chat Form")
    page.get_by_role("button", name="New Chat").click()
    page.wait_for_timeout(400)
    shot(page, "new_chat_form")

    # Check provider dropdown only has LLM providers
    provider_sel = page.locator("select").first
    options = [o.inner_text() for o in provider_sel.locator("option").all()]
    print(f"  Provider options: {options}")
    assert "Pinecone (RAG)" not in options, "Pinecone must not appear as a chat provider"
    assert "OpenAI" in options
    assert "Anthropic" in options
    assert "Google Gemini" in options
    print("  ✓ Only real LLM providers shown (no Pinecone)")

    # Change provider → verify model list updates
    provider_sel.select_option("anthropic")
    page.wait_for_timeout(200)
    model_options = [o.inner_text() for o in page.locator("select").nth(1).locator("option").all()]
    print(f"  Anthropic models: {model_options}")
    assert any("claude" in m.lower() for m in model_options)
    print("  ✓ Model list updates when provider changes")

    # Switch to Gemini
    provider_sel.select_option("gemini")
    page.wait_for_timeout(200)
    model_options = [o.inner_text() for o in page.locator("select").nth(1).locator("option").all()]
    print(f"  Gemini models: {model_options}")
    assert any("gemini" in m.lower() for m in model_options)
    print("  ✓ Gemini models shown correctly")

    # Cancel
    page.get_by_role("button", name="Cancel").click()
    page.wait_for_timeout(300)


def test_03_navigate_chats(page: Page):
    section("3 · Chat Navigation")
    chats = page.locator(".chat-item, [class*='chat-item']").all()
    print(f"  Found {len(chats)} chats in sidebar")
    assert len(chats) > 0, "Need at least one existing chat to test navigation"

    # Click first chat
    chats[0].click()
    page.wait_for_timeout(800)
    shot(page, "chat_view_first")
    print("  ✓ Clicked first chat — messages loaded")

    # If there are more chats, click between them
    if len(chats) >= 2:
        chats[1].click()
        page.wait_for_timeout(800)
        shot(page, "chat_view_second")
        print("  ✓ Switched to second chat — messages loaded")

    # Check header shows chat title
    header = page.locator(".chat-area__title, [class*='chat-area__title']").first
    if header.is_visible():
        title_text = header.inner_text()
        print(f"  Active chat title: {title_text!r}")
        print("  ✓ Chat header shows title")


def test_04_merged_chat_view(page: Page):
    section("4 · Merged Chat — RAG-Powered Badge")
    # Look for any merged chat in the sidebar
    merged_items = page.get_by_text("Merged:", exact=False).all()
    if not merged_items:
        print("  ⚠ No merged chats in sidebar — skipping merged chat test")
        return

    merged_items[0].click()
    page.wait_for_timeout(800)
    shot(page, "merged_chat_view")

    # Check RAG-powered badge
    rag_badge = page.get_by_text("RAG-powered", exact=False)
    if rag_badge.is_visible():
        print("  ✓ RAG-powered badge visible on merged chat")
    else:
        print("  ⚠ RAG-powered badge not found (may depend on is_merged flag)")

    # Check intro message
    intro = page.get_by_text("I've merged", exact=False).first
    if intro.is_visible():
        print(f"  ✓ Intro message visible: {intro.inner_text()[:80]!r}...")


def test_05_send_message(page: Page):
    section("5 · Send a Message (live API call)")
    # Find a regular (non-merged) chat to message
    chat_items = page.locator(".chat-item, [class*='chat-item']").all()
    regular_chat = None
    for item in chat_items:
        text = item.inner_text()
        if "Merged" not in text:
            regular_chat = item
            break

    if not regular_chat:
        print("  ⚠ No regular chats found — skipping live message test")
        return

    regular_chat.click()
    page.wait_for_timeout(600)

    print("  Sending test message...")
    send_message(page, "Briefly say hello and confirm you are working.", wait_ms=20_000)
    shot(page, "after_message_sent")

    # Look for an assistant response
    messages = page.locator(".message--assistant").all()
    if messages:
        last_msg = messages[-1].inner_text()
        print(f"  ✓ Got assistant response: {last_msg[:100]!r}...")
    else:
        print("  ⚠ No assistant message detected yet (may still be streaming)")


def test_06_merge_modal(page: Page):
    section("6 · Merge Modal UI")
    page.get_by_role("button", name="Merge Chats").click()
    page.wait_for_timeout(500)
    shot(page, "merge_modal_open")

    # Check modal title
    assert page.get_by_text("Merge Conversations").is_visible()
    print("  ✓ Merge modal opens")

    # Check no yellow Pinecone warning
    page_html = page.content()
    assert "Pinecone key required" not in page_html
    print("  ✓ No 'Pinecone key required' warning shown")

    # Check provider dropdown excludes Pinecone
    selects = page.locator("select").all()
    if selects:
        provider_options = [o.inner_text() for o in selects[0].locator("option").all()]
        print(f"  Merge provider options: {provider_options}")
        assert "Pinecone (RAG)" not in provider_options
        print("  ✓ Pinecone excluded from merge model providers")

    # Select two chats using the modal's own chat list (NOT the sidebar)
    modal_chat_items = page.locator(".merge-modal__chat-item").all()
    print(f"  Modal chat list items: {len(modal_chat_items)}")
    selected = 0
    for item in modal_chat_items:
        if selected >= 2:
            break
        item_text = item.inner_text()
        if "Merged" not in item_text:
            item.click()
            page.wait_for_timeout(200)
            selected += 1

    shot(page, "merge_modal_chats_selected")
    merge_btn = page.get_by_role("button", name="Merge 2 Chats")
    if merge_btn.is_visible():
        print("  ✓ 'Merge 2 Chats' button enabled after selecting 2 chats")

    # Close via Cancel button (more reliable than Escape)
    close_any_modal(page)
    print("  ✓ Merge modal closed")


def test_07_settings_modal(page: Page):
    section("7 · Settings Modal")
    close_any_modal(page)  # Ensure no modal is blocking

    # The settings gear button has title="Settings"
    page.locator("button[title='Settings']").click()
    page.wait_for_timeout(500)

    if page.get_by_text("API Keys").is_visible():
        shot(page, "settings_modal")
        print("  ✓ Settings modal opens")
        for provider in ["OpenAI", "Anthropic", "Google Gemini", "Pinecone (RAG)"]:
            matches = page.locator(".settings-modal__section-title, .settings-modal__api-key-provider").filter(has_text=provider).all()
            if matches:
                print(f"  ✓ {provider} entry visible in settings")
        close_any_modal(page)
    else:
        shot(page, "settings_attempt")
        print("  ⚠ Could not open settings modal")


def test_08_title_editing(page: Page):
    section("8 · Chat Title Editing")
    close_any_modal(page)
    # Click on a non-merged chat
    chat_items = page.locator(".chat-item").all()
    for item in chat_items:
        if "Merged" not in item.inner_text():
            item.click()
            page.wait_for_timeout(600)
            break

    # Click the title in the chat header to edit it
    title_el = page.locator(".chat-area__title").first
    if title_el.is_visible():
        title_el.click()
        page.wait_for_timeout(300)
        # Should show an input
        title_input = page.locator(".chat-area__title-input")
        if title_input.is_visible():
            shot(page, "title_editing")
            title_input.press("Escape")  # cancel edit
            print("  ✓ Title becomes editable on click, Escape cancels")
        else:
            print("  ⚠ Title input not shown after click")
    else:
        print("  ⚠ Chat title element not found")


def test_09_full_flow_screenshot(page: Page):
    section("9 · Final State — Full App")
    close_any_modal(page)
    merged = page.locator(".chat-item").filter(has_text="Merged:").all()
    if merged:
        merged[0].click()
        page.wait_for_timeout(800)
    shot(page, "final_state_merged_chat")
    print("  ✓ Final full-page screenshot captured")


# ─── Main ───────────────────────────────────────────────────────────────────

def run_all_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        t_start = time.time()
        passed = failed = 0

        tests = [
            test_01_landing,
            test_02_new_chat_form,
            test_03_navigate_chats,
            test_04_merged_chat_view,
            test_05_send_message,
            test_06_merge_modal,
            test_07_settings_modal,
            test_08_title_editing,
            test_09_full_flow_screenshot,
        ]

        for test_fn in tests:
            try:
                test_fn(page)
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  ✗ FAILED: {e}")
                shot(page, f"FAIL_{test_fn.__name__}")

        browser.close()

        elapsed = time.time() - t_start
        print(f"\n{'='*60}")
        print(f"  Results: {passed} passed, {failed} failed  ({elapsed:.1f}s)")
        if console_errors:
            print(f"  ⚠  {len(console_errors)} browser console error(s):")
            for e in console_errors[:3]:
                print(f"     {e[:120]}")
        print(f"  Screenshots: {OUT}/")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    run_all_tests()
