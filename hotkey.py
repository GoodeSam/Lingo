"""
Global hotkey via NSEvent global monitor.
Requires Input Monitoring permission (macOS will prompt automatically).
"""
import logging
import Cocoa

log = logging.getLogger(__name__)

kVK_ANSI_T = 0x11
kVK_ANSI_O = 0x1F

# Legacy Carbon modifier constants (used by callers)
cmdKey     = 0x0100
shiftKey   = 0x0200
optionKey  = 0x0800
controlKey = 0x1000

_RELEVANT = (
    Cocoa.NSEventModifierFlagCommand
    | Cocoa.NSEventModifierFlagShift
    | Cocoa.NSEventModifierFlagControl
    | Cocoa.NSEventModifierFlagOption
)

_monitors: list = []


def register(hotkey_id: int, key_code: int, modifiers: int, callback) -> bool:
    """Register a global key-down hotkey. Returns True on success, False if Input Monitoring permission is missing."""
    ns_mods = 0
    if modifiers & 0x0100:
        ns_mods |= Cocoa.NSEventModifierFlagCommand
    if modifiers & 0x0200:
        ns_mods |= Cocoa.NSEventModifierFlagShift
    if modifiers & 0x0800:
        ns_mods |= Cocoa.NSEventModifierFlagOption
    if modifiers & 0x1000:
        ns_mods |= Cocoa.NSEventModifierFlagControl

    def handler(event):
        if event.isARepeat():
            return
        if event.keyCode() == key_code and (event.modifierFlags() & _RELEVANT) == ns_mods:
            callback()

    monitor = Cocoa.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        Cocoa.NSEventMaskKeyDown, handler
    )
    if monitor is None:
        log.warning("Hotkey registration failed — Input Monitoring permission not granted")
    else:
        log.debug("Hotkey registered OK")
        _monitors.append(monitor)
    return monitor is not None
