"""
Floating result panel — appears near cursor, dismisses on click-away or Esc.
"""
import Cocoa
import objc
import audio as _audio


class _ClickHandler(Cocoa.NSObject):
    _callback = objc.ivar()

    def handleClick_(self, sender):
        if self._callback:
            self._callback()


class _PanelDelegate(Cocoa.NSObject):
    _on_close = objc.ivar()

    def windowWillClose_(self, notification):
        if self._on_close:
            self._on_close()


def _copy_to_clipboard(text: str):
    pb = Cocoa.NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, Cocoa.NSPasteboardTypeString)


def _audio_safe(text: str):
    try:
        _audio.speak(text)
    except Exception:
        pass


_PANEL_BG    = Cocoa.NSColor.colorWithRed_green_blue_alpha_(0.14, 0.14, 0.16, 1.0)
_TEXT_WHITE  = Cocoa.NSColor.whiteColor()
_TEXT_GRAY   = Cocoa.NSColor.colorWithRed_green_blue_alpha_(0.60, 0.60, 0.65, 1.0)
_TEXT_YELLOW = Cocoa.NSColor.colorWithRed_green_blue_alpha_(0.98, 0.82, 0.40, 1.0)
_TEXT_GREEN  = Cocoa.NSColor.colorWithRed_green_blue_alpha_(0.45, 0.85, 0.60, 1.0)
_PANEL_W     = 540
_PAD         = 20
_PAD_TOP     = 24
_CORNER_R    = 14.0


def _attr(text: str, color, size: float, bold: bool = False) -> Cocoa.NSAttributedString:
    weight = Cocoa.NSFontWeightSemibold if bold else Cocoa.NSFontWeightRegular
    font = Cocoa.NSFont.systemFontOfSize_weight_(size, weight)
    return Cocoa.NSAttributedString.alloc().initWithString_attributes_(
        text,
        {
            Cocoa.NSFontAttributeName: font,
            Cocoa.NSForegroundColorAttributeName: color,
        },
    )


def _make_label(attributed: Cocoa.NSAttributedString, frame) -> Cocoa.NSTextField:
    field = Cocoa.NSTextField.labelWithAttributedString_(attributed)
    field.setFrame_(frame)
    field.setMaximumNumberOfLines_(0)
    field.setLineBreakMode_(Cocoa.NSLineBreakByWordWrapping)
    field.setDrawsBackground_(False)
    field.setBezeled_(False)
    field.setEditable_(False)
    field.setSelectable_(True)
    return field


def _cursor_pos() -> tuple[float, float]:
    loc = Cocoa.NSEvent.mouseLocation()
    return loc.x, loc.y


def _screen_for_point(x: float, y: float):
    pt = Cocoa.NSMakePoint(x, y)
    for screen in Cocoa.NSScreen.screens():
        if Cocoa.NSPointInRect(pt, screen.frame()):
            return screen
    return Cocoa.NSScreen.mainScreen()


class ResultPanel:
    def __init__(self):
        self._panel: Cocoa.NSPanel | None = None
        self._monitor = None
        self._key_monitor = None
        self._audio_handler = None
        self._copy_handler = None
        self._delegate = None

    def show(self, result: dict):
        self.hide()
        Cocoa.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        mode = result.get("mode", "sentence")
        word = result.get("word", "")
        view, height = (
            self._word_view(result, lambda: _audio_safe(word))
            if mode == "word" else self._sentence_view(result)
        )

        mx, my = _cursor_pos()
        screen = _screen_for_point(mx, my).visibleFrame()

        # Cap height to screen and wrap in a scroll view if content overflows
        max_h = screen.size.height - 32
        if height > max_h:
            scroll = Cocoa.NSScrollView.alloc().initWithFrame_(
                Cocoa.NSMakeRect(0, 0, _PANEL_W, max_h)
            )
            scroll.setDocumentView_(view)
            scroll.setHasVerticalScroller_(True)
            scroll.setAutohidesScrollers_(True)
            scroll.setBorderType_(Cocoa.NSNoBorder)
            scroll.setDrawsBackground_(False)
            view, height = scroll, max_h

        px = max(screen.origin.x + 16, min(mx, screen.origin.x + screen.size.width - _PANEL_W - 16))
        py = max(screen.origin.y + 16, min(my + 12, screen.origin.y + screen.size.height - height - 16))

        panel = Cocoa.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            Cocoa.NSMakeRect(px, py, _PANEL_W, height),
            (
                Cocoa.NSWindowStyleMaskTitled
                | Cocoa.NSWindowStyleMaskClosable
                | Cocoa.NSWindowStyleMaskNonactivatingPanel
                | Cocoa.NSWindowStyleMaskFullSizeContentView
            ),
            Cocoa.NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(Cocoa.NSFloatingWindowLevel)
        panel.setTitlebarAppearsTransparent_(True)
        panel.setTitleVisibility_(Cocoa.NSWindowTitleHidden)
        panel.setMovableByWindowBackground_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(Cocoa.NSColor.clearColor())

        content = panel.contentView()
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(_CORNER_R)
        content.layer().setMasksToBounds_(True)
        content.layer().setBackgroundColor_(_PANEL_BG.CGColor())

        # Delegate funnels ✕-button / Cmd-W closes through the same cleanup path
        delegate = _PanelDelegate.alloc().init()
        delegate._on_close = self._do_cleanup
        panel.setDelegate_(delegate)
        self._delegate = delegate

        content.addSubview_(view)
        panel.makeKeyAndOrderFront_(None)
        self._panel = panel

        self._monitor = Cocoa.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            Cocoa.NSEventMaskLeftMouseDown | Cocoa.NSEventMaskRightMouseDown,
            self._outside_click,
        )
        self._key_monitor = Cocoa.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            Cocoa.NSEventMaskKeyDown,
            self._handle_key,
        )

    def _handle_key(self, event):
        if event.keyCode() == 53:  # Escape
            self.hide()
            return None
        return event

    def _outside_click(self, event):
        if self._panel:
            mouse = Cocoa.NSEvent.mouseLocation()
            if not Cocoa.NSPointInRect(mouse, self._panel.frame()):
                self.hide()

    def _do_cleanup(self):
        if self._monitor:
            Cocoa.NSEvent.removeMonitor_(self._monitor)
            self._monitor = None
        if self._key_monitor:
            Cocoa.NSEvent.removeMonitor_(self._key_monitor)
            self._key_monitor = None
        self._audio_handler = None
        self._copy_handler = None
        self._delegate = None
        self._panel = None

    def hide(self):
        panel = self._panel
        self._do_cleanup()
        if panel:
            panel.close()

    # ── Word view ──────────────────────────────────────────────────────────
    def _word_view(self, r: dict, on_audio) -> tuple[Cocoa.NSView, float]:
        btn_size = 32
        text_x = _PAD
        text_w = _PANEL_W - _PAD * 2
        y = _PAD_TOP + btn_size + 10
        views = []

        def add(text, color, size, bold=False, top_gap=0):
            nonlocal y
            y += top_gap
            a = _attr(text, color, size, bold)
            rect = a.boundingRectWithSize_options_context_(
                Cocoa.NSMakeSize(text_w, 9999),
                Cocoa.NSStringDrawingUsesLineFragmentOrigin,
                None,
            )
            h = rect.size.height + 2
            views.append(_make_label(a, Cocoa.NSMakeRect(text_x, y, text_w, h)))
            y += h

        def add_sep(top_gap=10):
            nonlocal y
            y += top_gap
            sep = Cocoa.NSView.alloc().initWithFrame_(
                Cocoa.NSMakeRect(_PAD, y, _PANEL_W - _PAD * 2, 1)
            )
            sep.setWantsLayer_(True)
            sep.layer().setBackgroundColor_(
                Cocoa.NSColor.colorWithWhite_alpha_(1.0, 0.10).CGColor()
            )
            views.append(sep)
            y += 1

        add(r.get("original", r.get("word", "")), _TEXT_WHITE, 20, bold=True)
        add(r.get("zh_translation", ""), _TEXT_YELLOW, 20, bold=True, top_gap=6)

        add_sep(top_gap=12)

        ipa = r.get("ipa", "")
        pos = r.get("part_of_speech", "")
        meta = "  •  ".join(p for p in [ipa, pos] if p)
        if meta:
            add(meta, _TEXT_GRAY, 14, top_gap=10)
        add(r.get("en_definition", ""), _TEXT_WHITE, 17, top_gap=6)
        ex = r.get("example", "")
        if ex:
            add(f'"{ex}"', _TEXT_GREEN, 16, top_gap=8)

        total_h = y + _PAD
        container = Cocoa.NSView.alloc().initWithFrame_(
            Cocoa.NSMakeRect(0, 0, _PANEL_W, total_h)
        )
        for v in views:
            f = v.frame()
            f.origin.y = total_h - f.origin.y - f.size.height
            v.setFrame_(f)
            container.addSubview_(v)

        btn = Cocoa.NSButton.alloc().initWithFrame_(
            Cocoa.NSMakeRect(_PAD, total_h - _PAD_TOP - btn_size, btn_size, btn_size)
        )
        btn.setTitle_("🔊")
        btn.setBordered_(False)
        btn.setFont_(Cocoa.NSFont.systemFontOfSize_(20))
        handler = _ClickHandler.alloc().init()

        def on_audio_click():
            btn.setTitle_("🔉")
            on_audio()
            Cocoa.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.0, False, lambda t: btn.setTitle_("🔊")
            )

        handler._callback = on_audio_click
        btn.setTarget_(handler)
        btn.setAction_(objc.selector(handler.handleClick_, signature=b"v@:@"))
        self._audio_handler = handler
        container.addSubview_(btn)

        _word  = r.get("original", r.get("word", ""))
        _ipa   = r.get("ipa", "")
        _zh    = r.get("zh_translation", "")
        _pos   = r.get("part_of_speech", "")
        _def   = r.get("en_definition", "")
        _ex    = r.get("example", "")
        _parts = []
        if _word or _ipa:
            _parts.append(f"{_word}  {_ipa}".strip() if _ipa else _word)
        if _pos:
            _parts.append(_pos)
        if _zh:
            _parts.append(_zh)
        if _def:
            _parts.append(_def)
        if _ex:
            _parts.append(f'"{_ex}"')
        copy_text = "\n".join(_parts)

        copy_btn = Cocoa.NSButton.alloc().initWithFrame_(
            Cocoa.NSMakeRect(_PAD + btn_size + 4, total_h - _PAD_TOP - btn_size, btn_size, btn_size)
        )
        copy_btn.setTitle_("📋")
        copy_btn.setBordered_(False)
        copy_btn.setFont_(Cocoa.NSFont.systemFontOfSize_(18))
        copy_handler = _ClickHandler.alloc().init()

        def on_copy():
            _copy_to_clipboard(copy_text)
            copy_btn.setTitle_("✅")
            Cocoa.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.5, False, lambda t: copy_btn.setTitle_("📋")
            )

        copy_handler._callback = on_copy
        copy_btn.setTarget_(copy_handler)
        copy_btn.setAction_(objc.selector(copy_handler.handleClick_, signature=b"v@:@"))
        self._copy_handler = copy_handler
        container.addSubview_(copy_btn)

        on_audio()
        return container, total_h

    # ── Sentence view ──────────────────────────────────────────────────────
    def _sentence_view(self, r: dict) -> tuple[Cocoa.NSView, float]:
        btn_size = 32
        text_x = _PAD
        text_w = _PANEL_W - _PAD * 2
        y = _PAD_TOP + btn_size + 10
        views = []
        original = r.get("original", "")
        zh = r.get("zh_translation", "")

        def add(text, color, size, bold=False, top_gap=0):
            nonlocal y
            y += top_gap
            a = _attr(text, color, size, bold)
            rect = a.boundingRectWithSize_options_context_(
                Cocoa.NSMakeSize(text_w, 9999),
                Cocoa.NSStringDrawingUsesLineFragmentOrigin,
                None,
            )
            h = rect.size.height + 2
            views.append(_make_label(a, Cocoa.NSMakeRect(text_x, y, text_w, h)))
            y += h

        def add_sep(top_gap=10):
            nonlocal y
            y += top_gap
            sep = Cocoa.NSView.alloc().initWithFrame_(
                Cocoa.NSMakeRect(_PAD, y, _PANEL_W - _PAD * 2, 1)
            )
            sep.setWantsLayer_(True)
            sep.layer().setBackgroundColor_(
                Cocoa.NSColor.colorWithWhite_alpha_(1.0, 0.10).CGColor()
            )
            views.append(sep)
            y += 1

        if original:
            preview = original if len(original) <= 150 else original[:148] + "…"
            add(preview, _TEXT_WHITE, 17)

        add_sep(top_gap=12)

        add(zh, _TEXT_YELLOW, 19, bold=True, top_gap=10)
        note = r.get("note", "")
        if note:
            add(f"💡 {note}", _TEXT_GRAY, 14, top_gap=10)

        total_h = y + _PAD
        container = Cocoa.NSView.alloc().initWithFrame_(
            Cocoa.NSMakeRect(0, 0, _PANEL_W, total_h)
        )
        for v in views:
            f = v.frame()
            f.origin.y = total_h - f.origin.y - f.size.height
            v.setFrame_(f)
            container.addSubview_(v)

        on_audio = lambda: _audio_safe(original) if original else None
        btn = Cocoa.NSButton.alloc().initWithFrame_(
            Cocoa.NSMakeRect(_PAD, total_h - _PAD_TOP - btn_size, btn_size, btn_size)
        )
        btn.setTitle_("🔊")
        btn.setBordered_(False)
        btn.setFont_(Cocoa.NSFont.systemFontOfSize_(20))
        handler = _ClickHandler.alloc().init()

        def on_audio_click():
            btn.setTitle_("🔉")
            on_audio()
            Cocoa.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.0, False, lambda t: btn.setTitle_("🔊")
            )

        handler._callback = on_audio_click
        btn.setTarget_(handler)
        btn.setAction_(objc.selector(handler.handleClick_, signature=b"v@:@"))
        self._audio_handler = handler
        container.addSubview_(btn)

        copy_text = "\n".join(p for p in [original, zh] if p)
        copy_btn = Cocoa.NSButton.alloc().initWithFrame_(
            Cocoa.NSMakeRect(_PAD + btn_size + 4, total_h - _PAD_TOP - btn_size, btn_size, btn_size)
        )
        copy_btn.setTitle_("📋")
        copy_btn.setBordered_(False)
        copy_btn.setFont_(Cocoa.NSFont.systemFontOfSize_(18))
        copy_handler = _ClickHandler.alloc().init()

        def on_copy():
            _copy_to_clipboard(copy_text)
            copy_btn.setTitle_("✅")
            Cocoa.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.5, False, lambda t: copy_btn.setTitle_("📋")
            )

        copy_handler._callback = on_copy
        copy_btn.setTarget_(copy_handler)
        copy_btn.setAction_(objc.selector(copy_handler.handleClick_, signature=b"v@:@"))
        self._copy_handler = copy_handler
        container.addSubview_(copy_btn)

        on_audio()
        return container, total_h
