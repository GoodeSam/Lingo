"""
Text capture: tries AXUIElement first, falls back to clipboard simulation.
"""
import logging
import time
import Cocoa
import ApplicationServices as AS

log = logging.getLogger(__name__)


def get_selected_text() -> str | None:
    text = _ax_selected_text()
    if text:
        return text.strip() or None
    return _clipboard_fallback()


def _ax_selected_text() -> str | None:
    try:
        system = AS.AXUIElementCreateSystemWide()

        focused_app = AS.AXUIElementCopyAttributeValue(
            system, AS.kAXFocusedApplicationAttribute, None
        )
        if focused_app[0] != 0:
            log.debug("AX: no focused app (err %d)", focused_app[0])
            return None
        if focused_app[1] is None:
            return None

        focused_el = AS.AXUIElementCopyAttributeValue(
            focused_app[1], AS.kAXFocusedUIElementAttribute, None
        )
        if focused_el[0] != 0:
            log.debug("AX: no focused element (err %d)", focused_el[0])
            return None
        if focused_el[1] is None:
            return None

        # Refuse password fields
        is_password = AS.AXUIElementCopyAttributeValue(
            focused_el[1], "AXIsPasswordField", None
        )
        if is_password[0] == 0 and is_password[1]:
            log.debug("AX: skipping password field")
            return None

        selected = AS.AXUIElementCopyAttributeValue(
            focused_el[1], AS.kAXSelectedTextAttribute, None
        )
        if selected[0] == 0 and selected[1]:
            return str(selected[1])

        log.debug("AX: kAXSelectedTextAttribute err %d or empty", selected[0])
        return None

    except Exception as e:
        log.debug("AX capture exception (%s): %s", type(e).__name__, e)
        return None


# ── Clipboard snapshot helpers ─────────────────────────────────────────────

def _snapshot_clipboard(pb) -> list[dict]:
    """Return all items and their type/data from the pasteboard."""
    items = pb.pasteboardItems() or []
    snapshot = []
    for item in items:
        item_data = {}
        for t in (item.types() or []):
            data = item.dataForType_(t)
            if data is not None:
                item_data[t] = data
        if item_data:
            snapshot.append(item_data)
    return snapshot


def _restore_clipboard(pb, snapshot: list[dict]) -> None:
    pb.clearContents()
    if not snapshot:
        return
    ns_items = []
    for item_data in snapshot:
        ns_item = Cocoa.NSPasteboardItem.alloc().init()
        for t, data in item_data.items():
            ns_item.setData_forType_(data, t)
        ns_items.append(ns_item)
    pb.writeObjects_(ns_items)


# ── Clipboard fallback ─────────────────────────────────────────────────────

def _clipboard_fallback() -> str | None:
    pb = Cocoa.NSPasteboard.generalPasteboard()
    saved_count = pb.changeCount()
    snapshot = _snapshot_clipboard(pb)

    try:
        _simulate_copy()

        # Wait up to 400 ms for clipboard to change
        deadline = time.time() + 0.4
        while time.time() < deadline:
            if pb.changeCount() != saved_count:
                break
            time.sleep(0.05)

        if pb.changeCount() == saved_count:
            return None  # nothing was copied

        result = pb.stringForType_(Cocoa.NSPasteboardTypeString)
        return result.strip() if result else None

    finally:
        # Always restore, even if an exception occurred mid-copy
        if pb.changeCount() != saved_count:
            _restore_clipboard(pb, snapshot)


def _simulate_copy():
    import Quartz
    # Wait for hotkey modifier keys (⌘⌥) to be physically released before
    # posting Cmd+C — otherwise the app may see Cmd+Option+C instead.
    time.sleep(0.15)
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)
    c_down = Quartz.CGEventCreateKeyboardEvent(src, 0x08, True)   # kVK_ANSI_C
    c_up   = Quartz.CGEventCreateKeyboardEvent(src, 0x08, False)
    Quartz.CGEventSetFlags(c_down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventSetFlags(c_up,   0)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, c_down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, c_up)
