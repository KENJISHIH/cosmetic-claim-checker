# 化粧品宣稱檢核助手

依衛福部「化粧品標示宣傳廣告涉及虛偽誇大或醫療效能認定準則」（L0030099）四份附件，透過 Telegram Bot 快速判定宣稱文字是否合規、需要哪個等級的佐證。

## Stack

- Python 3.11
- [python-telegram-bot](https://python-telegram-bot.org/) v21（Bot 介面）
- [Anthropic Claude API](https://www.anthropic.com/) `claude-sonnet-4-6`（語意判讀）
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)（PDF OCR）
- 知識庫：241 筆詞句（`knowledge_base/attachments.json`）

## Setup

```bash
cp .env.example .env
# 填入以下變數：
```

| 變數 | 說明 | 取得方式 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot Token | [@BotFather](https://t.me/botfather) |
| `ALLOWED_USER_IDS` | 允許的 Telegram user_id（逗號分隔） | [@userinfobot](https://t.me/userinfobot) |
| `ANTHROPIC_API_KEY` | Claude API 金鑰 | [Anthropic Console](https://console.anthropic.com) |
| `ANTHROPIC_MODEL` | 模型（預設 claude-sonnet-4-6） | — |

## 啟動

```bash
pip3 install -r requirements.txt
python3 -m bot.main
```

## 測試

```bash
python3 -m pytest tests/ -v
```

## 使用方式

在 Telegram 傳訊息給你的 Bot：

- `/start` — 歡迎訊息與免責聲明
- `/check <宣稱文字>` — 檢核指定宣稱
- 直接傳文字 — 視同 `/check`

**範例：**

```
促進膠原蛋白合成     → ❌ 不可宣稱（附件一）
淡化黑眼圈          → 📋 合法但需 *1 佐證（附件二）
草本植萃            → ✅ 合法（附件二）
消除皺紋            → ❌ 不可宣稱（附件四）
```

## 知識庫重建（通常不需要）

```bash
# OCR 四份附件（需 Gemini CLI 登入）
python3 scripts/ocr_attachments.py

# 重新解析 → attachments.json
python3 scripts/build_kb.py

# 同步到 Obsidian
python3 scripts/sync_obsidian.py
```

## 免責聲明

本工具僅供初步參考，不構成法律建議。最終認定以衛生福利部食品藥物管理署（TFDA）及相關主管機關為準。
