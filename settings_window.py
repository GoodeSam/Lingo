"""Settings window — API key input."""
import Cocoa
import objc
import settings as _settings
import translate as _translate


class _SaveTarget(Cocoa.NSObject):
    _field = objc.ivar()
    _win   = objc.ivar()

    def save_(self, sender):
        key = self._field.stringValue()
        _settings.set("api_key", key)
        _translate._invalidate_client()
        self._win.close()


class SettingsWindowController:
    def __init__(self):
        self._win = None
        self._target = None

    def show(self):
        if self._win and self._win.isVisible():
            Cocoa.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self._win.makeKeyAndOrderFront_(None)
            return

        win = Cocoa.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            Cocoa.NSMakeRect(0, 0, 440, 150),
            (
                Cocoa.NSWindowStyleMaskTitled
                | Cocoa.NSWindowStyleMaskClosable
            ),
            Cocoa.NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("Lingo — Settings")
        win.center()

        content = win.contentView()

        lbl = Cocoa.NSTextField.labelWithString_("OpenAI API Key:")
        lbl.setFrame_(Cocoa.NSMakeRect(20, 100, 150, 22))
        content.addSubview_(lbl)

        field = Cocoa.NSSecureTextField.alloc().initWithFrame_(
            Cocoa.NSMakeRect(20, 68, 400, 26)
        )
        existing = _settings.get("api_key", "")
        if existing:
            field.setStringValue_(existing)
        field.setPlaceholderString_("sk-...")
        content.addSubview_(field)

        btn = Cocoa.NSButton.alloc().initWithFrame_(
            Cocoa.NSMakeRect(330, 24, 90, 28)
        )
        btn.setTitle_("Save")
        btn.setBezelStyle_(Cocoa.NSBezelStyleRounded)
        btn.setKeyEquivalent_("\r")
        content.addSubview_(btn)

        target = _SaveTarget.alloc().init()
        target._field = field
        target._win   = win
        btn.setTarget_(target)
        btn.setAction_(objc.selector(target.save_, signature=b"v@:@"))

        self._win    = win
        self._target = target  # keep alive

        Cocoa.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        win.makeKeyAndOrderFront_(None)
