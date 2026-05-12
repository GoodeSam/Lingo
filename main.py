"""
Lingo — free macOS English reading assistant.
Status bar app: global hotkey → capture text → OpenAI → floating result.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import Cocoa
import objc

logging.basicConfig(level=logging.WARNING)
_log = logging.getLogger(__name__)

import settings as _settings
import capture as _capture
import translate as _translate
import popover as _popover
import hotkey as _hotkey
import vocab as _vocab
from settings_window import SettingsWindowController


BLOCKED_APPS = {"1Password 7", "1Password", "Bitwarden", "Keychain Access"}
BROWSER_APPS = {"Safari", "Google Chrome", "Firefox", "Arc", "Brave Browser"}


def _frontmost_app_name() -> str:
    app = Cocoa.NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else ""


_PREF_ACCESSIBILITY    = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
_PREF_INPUT_MONITORING = "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"


def _check_accessibility() -> bool:
    import ApplicationServices as AS
    return AS.AXIsProcessTrusted()


def _request_accessibility():
    import ApplicationServices as AS
    opts = {AS.kAXTrustedCheckOptionPrompt: True}
    AS.AXIsProcessTrustedWithOptions(opts)


def _open_system_settings(url: str):
    Cocoa.NSWorkspace.sharedWorkspace().openURL_(Cocoa.NSURL.URLWithString_(url))


class AppDelegate(Cocoa.NSObject):
    _status_item  = objc.ivar()
    _panel        = objc.ivar()
    _settings_ctl = objc.ivar()

    def applicationDidFinishLaunching_(self, notification):
        self._panel = _popover.ResultPanel()
        self._settings_ctl = SettingsWindowController()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._req_id = 0
        self._req_lock = threading.Lock()
        self._pending_future = None

        # Status bar icon
        bar  = Cocoa.NSStatusBar.systemStatusBar()
        item = bar.statusItemWithLength_(Cocoa.NSVariableStatusItemLength)
        item.button().setTitle_("🔤")
        item.button().setToolTip_("Lingo")
        self._status_item = item

        menu = Cocoa.NSMenu.alloc().init()
        menu.addItemWithTitle_action_keyEquivalent_(
            "Translate selection  ⌘^T",
            objc.selector(self.menuTranslate_, signature=b"v@:@"),
            "",
        )
        menu.addItem_(Cocoa.NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_(
            "Export vocabulary…",
            objc.selector(self.menuExport_, signature=b"v@:@"),
            "",
        )
        menu.addItem_(Cocoa.NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_(
            "Quit Lingo",
            objc.selector(self.menuQuit_, signature=b"v@:@"),
            "q",
        )
        item.setMenu_(menu)

        # ── Permission: Accessibility ─────────────────────────────────────
        if not _check_accessibility():
            _request_accessibility()  # triggers macOS system dialog
            if not _check_accessibility():
                # User dismissed or hasn't granted yet — show manual guide
                self._showPermissionAlert(
                    "Accessibility Access Required",
                    "Lingo needs Accessibility access to read selected text.\n\n"
                    "Enable it in System Settings → Privacy & Security → Accessibility,\n"
                    "then relaunch Lingo.",
                    _PREF_ACCESSIBILITY,
                )

        if not _settings.get("api_key"):
            self._showError("OPENAI_API_KEY is not set.\nSet it in your shell profile and relaunch Lingo.")

        _log.debug("started")

        # ── Permission: Input Monitoring (global hotkey ⌘^T) ────────────
        try:
            ok = _hotkey.register(
                hotkey_id=1,
                key_code=_hotkey.kVK_ANSI_T,
                modifiers=_hotkey.cmdKey | _hotkey.controlKey,
                callback=self._onHotkey,
            )
            if not ok:
                self._showPermissionAlert(
                    "Input Monitoring Access Required",
                    "Lingo needs Input Monitoring access to detect the ⌘^T hotkey.\n\n"
                    "Enable it in System Settings → Privacy & Security → Input Monitoring,\n"
                    "then relaunch Lingo.\n\n"
                    "You can still use Translate selection (⌘^T) from the 🔤 menu.",
                    _PREF_INPUT_MONITORING,
                )
        except Exception as e:
            _log.error("hotkey register failed: %s", e)

    # ── ObjC actions ──────────────────────────────────────────────────────

    def menuTranslate_(self, sender):
        self._runTranslate()

    def menuExport_(self, sender):
        words, sentences = _vocab.count()
        if words + sentences == 0:
            self._showError("No words recorded yet — translate something first!")
            return
        panel = Cocoa.NSSavePanel.savePanel()
        panel.setTitle_("Export Vocabulary")
        panel.setMessage_(f"{words} 个单词，{sentences} 个句子")
        panel.setNameFieldStringValue_("lingo_vocab.csv")
        panel.setAllowedFileTypes_(["csv"])
        if panel.runModal() == Cocoa.NSModalResponseOK:
            path = str(panel.URL().path())
            _vocab.export_csv(path)
            Cocoa.NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(path, "")

    def menuSettings_(self, sender):
        self._settings_ctl.show()

    def menuQuit_(self, sender):
        Cocoa.NSApplication.sharedApplication().terminate_(None)

    # ── Internal helpers (python_method = invisible to ObjC runtime) ───────

    @objc.python_method
    def _onHotkey(self):
        Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(self._runTranslate)

    @objc.python_method
    def _runTranslate(self):
        app_name = _frontmost_app_name()

        if app_name in BLOCKED_APPS:
            self._showError("Cannot capture text from this app for privacy reasons.")
            return

        if not _settings.get("api_key"):
            self._showError("No API key — open Settings from the Lingo menu.")
            self._settings_ctl.show()
            return

        with self._req_lock:
            self._req_id += 1
            req_id = self._req_id
            if self._pending_future:
                self._pending_future.cancel()

        self._pending_future = self._executor.submit(self._captureAndTranslate, app_name, req_id)

    @objc.python_method
    def _captureAndTranslate(self, app_name: str, req_id: int):
        text = _capture.get_selected_text()
        if not text:
            def _show_no_text():
                with self._req_lock:
                    if req_id != self._req_id:
                        return
                self._showError("No text selected — select text first, then press ⌘^T.")
            Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(_show_no_text)
            return

        if app_name in BROWSER_APPS and len(text) > 100:
            # Confirmation shown on main thread; req_id checked after user clicks Send
            # so a superseded request never reaches the OpenAI API.
            def on_main():
                if self._confirmSend(text, app_name):
                    with self._req_lock:
                        if req_id != self._req_id:
                            return
                    self._executor.submit(self._doTranslate, text, req_id)
            Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(on_main)
            return

        self._doTranslate(text, req_id)

    @objc.python_method
    def _doTranslate(self, text: str, req_id: int):
        with self._req_lock:
            if req_id != self._req_id:
                return
        try:
            result = _translate.translate(text)
            # Only record and display if this request is still current
            with self._req_lock:
                if req_id != self._req_id:
                    return
            _vocab.record(result, text)
            display = {**result, "original": text}
            Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._panel.show(display)
            )
        except _translate.TranslationError as e:
            _log.warning("translation error: %s", e)
            raw = str(e)
            if "api_key" in raw.lower() or "authentication" in raw.lower():
                msg = "Invalid API key — check your key in Settings."
            elif "timeout" in raw.lower():
                msg = "Request timed out — check your connection and try again."
            elif "refused" in raw.lower():
                msg = "OpenAI refused to translate this content."
            else:
                msg = f"Translation failed: {raw}"
            with self._req_lock:
                if req_id != self._req_id:
                    return
            Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._showError(msg)
            )
        except Exception as e:
            _log.error("unexpected error: %s %s", type(e).__name__, e)
            msg = f"Unexpected error: {type(e).__name__}"
            with self._req_lock:
                if req_id != self._req_id:
                    return
            Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._showError(msg)
            )

    @objc.python_method
    def _notify(self, msg: str):
        self._showError(msg)

    @objc.python_method
    def _showError(self, msg: str):
        alert = Cocoa.NSAlert.alloc().init()
        alert.setMessageText_("Lingo")
        alert.setInformativeText_(msg)
        alert.setAlertStyle_(Cocoa.NSAlertStyleWarning)
        alert.runModal()

    @objc.python_method
    def _confirmSend(self, text: str, app_name: str) -> bool:
        preview = text[:200] + ("…" if len(text) > 200 else "")
        alert = Cocoa.NSAlert.alloc().init()
        alert.setMessageText_(f"Send text from {app_name} to OpenAI?")
        alert.setInformativeText_(f'"{preview}"')
        alert.addButtonWithTitle_("Send")
        alert.addButtonWithTitle_("Cancel")
        return alert.runModal() == Cocoa.NSAlertFirstButtonReturn

    @objc.python_method
    def _showPermissionAlert(self, title: str, msg: str, settings_url: str):
        alert = Cocoa.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(msg)
        alert.addButtonWithTitle_("Open System Settings")
        alert.addButtonWithTitle_("Later")
        if alert.runModal() == Cocoa.NSAlertFirstButtonReturn:
            _open_system_settings(settings_url)


def main():
    app = Cocoa.NSApplication.sharedApplication()
    app.setActivationPolicy_(Cocoa.NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
