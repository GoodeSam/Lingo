"""Persistent settings — API key read from env var, other prefs in NSUserDefaults."""
import os
import Cocoa

_SUITE = "com.lingo.app"


def _defaults():
    return Cocoa.NSUserDefaults.alloc().initWithSuiteName_(_SUITE)


def get(key: str, fallback=None):
    if key == "api_key":
        return os.environ.get("OPENAI_API_KEY") or fallback
    val = _defaults().objectForKey_(key)
    return val if val is not None else fallback


def set(key: str, value):
    if key == "api_key":
        return  # env var is read-only; ignore writes
    d = _defaults()
    d.setObject_forKey_(value, key)
    d.synchronize()
