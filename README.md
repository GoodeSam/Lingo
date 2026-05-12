# Lingo

A free macOS app that translates English anywhere on your screen using OpenAI. Select a word, sentence, or paragraph — press a hotkey — get an instant result.

## Requirements

- macOS 13 or later
- Python 3.11+
- An OpenAI API key (`sk-...`)

## Install

```bash
git clone https://github.com/yourname/lingo.git
cd lingo
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

The 🔤 icon appears in your menu bar. The app runs silently in the background with no Dock icon.

## First-time setup

### 1. Add your OpenAI API key

Click **🔤 → Settings…** → paste your `sk-...` key → press Enter.

### 2. Grant permissions

macOS requires two permissions. Lingo requests both automatically at launch and guides you to the correct settings page.

| Permission       | What it enables                    | Where to grant                                          |
| ---------------- | ---------------------------------- | ------------------------------------------------------- |
| Accessibility    | Read selected text without copying | System Settings → Privacy & Security → Accessibility    |
| Input Monitoring | Global hotkey (`⌘^T`)              | System Settings → Privacy & Security → Input Monitoring |

After granting permissions, relaunch the app:

```bash
./run.sh
```

## Usage

### Check a word or translate text

1. Select any text in any app (browser, Terminal, PDF viewer, editor…)
2. Press **`⌘^T`** (Command+Control+T)
3. A dark panel appears near your cursor with the result
4. Click anywhere to dismiss

### Word lookup

Select a single word → press `⌘^T`

```
有弹性的，适应力强的
resilient  /rɪˈzɪliənt/  adj.
able to recover quickly from difficulties
"The resilient team overcame every obstacle."
```

- The word is **read aloud automatically** when the panel opens
- Click **🔊** in the top-right corner to replay the pronunciation

### Sentence / paragraph translation

Select a sentence or paragraph → press `⌘^T`

```
这个坚韧的团队克服了每一个障碍。
💡 "resilient" carries a nuance of bouncing back, stronger than just "strong".
```

## Vocabulary journal

Every translation is saved locally to `~/.lingo_vocab.json`. The same word or sentence looked up multiple times accumulates a **query count**.

### Export

Click **🔤 → Export vocabulary…** to save a CSV file. The file opens directly in Finder after export.

CSV columns: `类型 | 单词/原文 | 音标 | 词性 | 英文释义 | 中文翻译 | 例句/备注 | 查询次数 | 首次查询 | 最近查询`

Words are sorted by query count (most-looked-up first), followed by sentences. The file is UTF-8 BOM encoded so Excel opens it correctly without manual import steps.

## Menu bar

Click **🔤** to access:

| Item                    | Action                                       |
| ----------------------- | -------------------------------------------- |
| Translate selection ⌘^T | Translate currently selected text            |
| Export vocabulary…      | Save all recorded words and sentences to CSV |
| Settings…               | Change your OpenAI API key                   |
| Quit Lingo              | Stop the app                                 |

## Privacy

- Text is sent to OpenAI only when you trigger a translation
- Long text from browser apps shows a confirmation prompt before sending
- Password fields and password manager apps are never captured
- Recent results are cached in memory — repeated lookups within a session make no API call
- The vocabulary journal is stored locally and never uploaded

## Troubleshooting

**Hotkey does nothing**
Grant Input Monitoring in System Settings → Privacy & Security → Input Monitoring, then relaunch. You can still use Translate selection from the 🔤 menu in the meantime.

**"No text selected"**
Select text first, then press `⌘^T`. Some apps block programmatic text access — try selecting and copying manually first.

**"Invalid API key"**
Open Settings… from the menu bar and re-enter your key. Make sure it starts with `sk-`.

**"Request timed out"**
Check your internet connection. Long paragraphs occasionally take longer — select a shorter passage.

## License

MIT

pasting

粘贴



在显示面板上增加一个复制按钮，可以使查询到的内容复制到剪贴板，以便于后续的粘贴。

Add a copy button to the display panel so

  that the queried content can be copied to the clipboard

  for subsequent pasting.

Change the layout to text is in another line behind \[🔊]\[📋] button 

After press the buttons,there should be different to show the buttons have been pressed.

After press the copy button, the English words, IPA, Chinese translatin ,example sentence should be copied too. Users can paste them too

```javascript
⏺ Done. For word mode, pressing 📋 now copies a formatted block
  like:

  hello  /həˈloʊ/
  adjective
  你好
  A greeting used to attract attention.
  "Hello, how are you today?"

  Each field (IPA, part of speech, Chinese translation, English
  definition, example) is only included if present, so missing
  fields don't leave blank lines.
```

lines  /laɪnz/

noun

线

Plural form of line; a long, narrow mark or band.

"The artist drew several lines to create the outline of the drawing."

The artist drew several lines to create the outline of the drawing.

艺术家画了几条线来勾勒画作的轮廓。



Push /Users/victor/projects/lingo to github:

git remote add origin [git\@github.com](mailto:git@github.com):GoodeSam/Lingo.git

git branch -M main

git push -u origin main
