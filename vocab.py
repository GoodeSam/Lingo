"""Vocabulary journal — tracks query count per word/sentence, exports to CSV."""
import csv
import datetime
import json
import pathlib
import threading

_lock = threading.Lock()

_STORE = pathlib.Path.home() / ".lingo_vocab.json"
_OLD_STORE = pathlib.Path.home() / ".lingo_vocab.jsonl"


def _load() -> dict:
    if _STORE.exists():
        try:
            data = json.loads(_STORE.read_text(encoding="utf-8"))
            if "words" in data and "sentences" in data:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    data = {"words": {}, "sentences": {}}
    _migrate_jsonl(data)
    return data


def _save(data: dict):
    tmp = _STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_STORE)


def _migrate_jsonl(data: dict):
    """One-time import of old append-only JSONL into the new format."""
    if not _OLD_STORE.exists():
        return
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _OLD_STORE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = e.get("ts", now)
            if e.get("mode") == "word":
                key = e.get("word", "").lower()
                if key:
                    existing = data["words"].get(key, {})
                    data["words"][key] = {**e, "count": existing.get("count", 0) + 1,
                                          "first_seen": existing.get("first_seen", ts),
                                          "last_seen": ts}
            else:
                key = e.get("original", "")[:100]
                if key:
                    existing = data["sentences"].get(key, {})
                    data["sentences"][key] = {**e, "count": existing.get("count", 0) + 1,
                                              "first_seen": existing.get("first_seen", ts),
                                              "last_seen": ts}
    _OLD_STORE.rename(_OLD_STORE.with_suffix(".jsonl.bak"))


def record(result: dict, original_text: str = ""):
    with _lock:
        data = _load()
        now = datetime.datetime.now().isoformat(timespec="seconds")

        if result.get("mode") == "word":
            key = result.get("word", original_text).lower()
            existing = data["words"].get(key, {})
            data["words"][key] = {
                "word":           result.get("word", original_text),
                "ipa":            result.get("ipa", ""),
                "part_of_speech": result.get("part_of_speech", ""),
                "en_definition":  result.get("en_definition", ""),
                "zh_translation": result.get("zh_translation", ""),
                "example":        result.get("example", ""),
                "count":          existing.get("count", 0) + 1,
                "first_seen":     existing.get("first_seen", now),
                "last_seen":      now,
            }
        else:
            key = original_text[:100]
            existing = data["sentences"].get(key, {})
            data["sentences"][key] = {
                "original":       original_text,
                "zh_translation": result.get("zh_translation", ""),
                "note":           result.get("note", ""),
                "count":          existing.get("count", 0) + 1,
                "first_seen":     existing.get("first_seen", now),
                "last_seen":      now,
            }

        _save(data)


def count() -> tuple[int, int]:
    with _lock:
        data = _load()
        return len(data["words"]), len(data["sentences"])


def export_csv(path: str):
    with _lock:
        data = _load()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM → Excel 不乱码
        w = csv.writer(f)
        w.writerow(["类型", "单词 / 原文", "音标", "词性", "英文释义", "中文翻译", "例句 / 备注", "查询次数", "首次查询", "最近查询"])

        for e in sorted(data["words"].values(), key=lambda x: x["count"], reverse=True):
            w.writerow(["单词", e.get("word", ""), e.get("ipa", ""), e.get("part_of_speech", ""),
                        e.get("en_definition", ""), e.get("zh_translation", ""), e.get("example", ""),
                        e.get("count", 1), e.get("first_seen", ""), e.get("last_seen", "")])

        for e in sorted(data["sentences"].values(), key=lambda x: x["count"], reverse=True):
            w.writerow(["句子", e.get("original", ""), "", "", "",
                        e.get("zh_translation", ""), e.get("note", ""),
                        e.get("count", 1), e.get("first_seen", ""), e.get("last_seen", "")])
