---
name: 化粧品宣稱檢核助手
codename: cosmetic-claim-checker
tg_username: "@cosmetic_claim_bot"
owner: Kenji Shih (kenjishih@gmail.com)
created: 2026-04-22
handoff_to: Claude Sonnet 4.6
current_phase: Phase 3 完成，待啟動 Phase 2（/addcase 案例累積）
last_updated: 2026-04-22
---

# 化粧品宣稱檢核助手 — 開發執行書

> **狀態（2026-04-22 更新）**：Phase 0、1、3 已完成，Fly.io 東京 24/7 上線中（`cosmetic-claim-checker.fly.dev`）。這份文件保留原始規劃供追溯；實作細節以 `~/Documents/Kenji_Vault/Kenji_Vault/02_Project_Claude/Work_Logs/2026-04-22_cosmetic-claim-checker.md` 為準。下一步是 Phase 2（`/addcase` 指令 + 案例 few-shot 整合）。

---

## 0. 專案快覽

| 項目 | 內容 |
|---|---|
| 中文名稱 | 化粧品宣稱檢核助手（備選：化粧品宣稱檢核工具 / 化粧品宣稱合規小幫手） |
| Telegram Bot | `@cosmetic_claim_bot` |
| 專案位置 | `~/Documents/KJ-agent/cosmetic-claim-checker/` |
| 主語言 | Python 3.11 |
| LLM | Claude API（`ANTHROPIC_API_KEY`，模型先用 `claude-sonnet-4-6`，成本敏感時再切） |
| 部署目標 | Fly.io 東京區（Phase 3，先不用管） |
| 使用者 | **單人模式**：只接 Kenji 本人的 Telegram user_id；他人訊息回「服務測試中」 |
| 主法源 | https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099 |

---

## 1. 背景與目標

### 1.1 要解決什麼問題
Kenji 工作上常被朋友詢問「這個化妝品文案可不可以這樣寫」。現行做法是人工比對衛福部公告的四份附件，效率低、易遺漏。目標是把這四份附件 + 案例累積起來，透過 Telegram Bot 快速查詢。

### 1.2 使用情境
```
朋友 ─ LINE/訊息 ─→ Kenji
                      │
                      ↓（手機開 Telegram）
                   @cosmetic_claim_bot
                      │
                      ↓（貼上宣稱關鍵字或完整文案）
                   判定結果 + 佐證需求 + 免責聲明
                      │
                      ↓（截圖）
Kenji ─ 截圖回覆 ─→ 朋友
```

### 1.3 判定的三層思維（來自 Kenji 口述的法律框架）

1. **越界類（Tier 0）**：涉醫療效能或影響生理機能/改變身體結構的宣稱 → **不可宣稱**，不是做實驗就能合法化
2. **合法化粧品宣稱（Tier 1）**：保濕、清潔、去油、柔順等 → 可宣稱，進入佐證強度討論
3. **佐證強度**：依星號分級 `*1` ～ `*5`，功能性越強、佐證要求越高

---

## 2. 整體架構

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Bot 介面                      │
│          (python-telegram-bot, 單人白名單模式)            │
└───────────────────────┬─────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              │                    │
   ┌──────────▼─────────┐  ┌──────▼─────────┐
   │   關鍵字比對器       │  │  LLM 判讀器       │
   │ (attachments.json) │  │ (Claude API)   │
   │  - 精確匹配         │  │  - Tier 0 越界  │
   │  - 子字串匹配       │  │  - 語意相似     │
   │  - 類別搜尋         │  │  - 案例參考     │
   └──────────┬─────────┘  └──────┬─────────┘
              │                    │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │   回覆組裝器        │
              │ - 判定層級           │
              │ - 命中詞句+出處      │
              │ - 佐證需求說明       │
              │ - 免責聲明（固定）   │
              └────────────────────┘
```

---

## 3. 知識庫設計（核心）

### 3.1 四份附件分類對應

| 附件 | 檔名 | 內容性質 | 判定結果 | 佐證需求 |
|---|---|---|---|---|
| 附件一 | 涉及影響生理機能或改變身體結構之詞句 | **越界清單** | ❌ 不可宣稱 | — |
| 附件二 | 通常得使用之詞句例示或類似之詞句 | **合法詞句 + 星號分級** | ✅ 合法 | 依 `*1`～`*5` 分級 |
| 附件三 | 成分之生理機能詞句例示或類似之詞句 | **成分型宣稱** | ⚠️ 需以特定成分為前提 | 成分 + 相應佐證 |
| 附件四 | 涉及其他醫療效能之詞句 | **越界清單** | ❌ 不可宣稱 | — |

### 3.2 附件二星號註解（必須內建於回覆）

```
*1 → 必須具備客觀且公正試驗數據佐證
*2 → 法施行 5 年後須符合化粧品產品資訊檔案管理辦法規定，
     含客觀且公正科學性佐證或其他足以證明功效者
*3 → 成分經國際或國內有機驗證機構驗證，並提出證明文件
*4 → 天然成分直接來自植物/動物/礦物，未添加其他非天然成分，
     或經國際/國內天然驗證機構驗證、符合 ISO 規範並提出證明
*5 → 產品通過國際或國內有機/天然驗證機構驗證，取得有機或天然標章，
     並經原驗證機構同意，提出有關證明文件
```
> 註六「產品具其他種類之特性者，詞句例示可流通使用」屬通則說明，不必掛在單一詞句。

### 3.3 統一資料 Schema（`knowledge_base/attachments.json`）

```json
{
  "metadata": {
    "source_law": "化粧品衛生安全管理法 / 化粧品之標示宣傳廣告涉及虛偽誇大或醫療效能認定準則",
    "law_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099",
    "last_updated": "2026-04-22",
    "star_notes": {
      "*1": "須具備客觀且公正試驗數據佐證",
      "*2": "須符合化粧品產品資訊檔案管理辦法規定...",
      "*3": "成分經有機驗證機構驗證，並提出證明文件",
      "*4": "天然成分直接來自動植礦物，未添加非天然成分...",
      "*5": "產品通過有機/天然驗證並取得標章..."
    }
  },
  "phrases": [
    {
      "id": "att2-eye-001",
      "phrase": "幫助/改善/淡化/調理黑眼圈",
      "source": "附件二",
      "category": "眼部保養",
      "verdict": "allowed_with_evidence",
      "star": "*1",
      "evidence_requirement": "需具備客觀且公正試驗數據",
      "raw_line": "（OCR 原文那一行）",
      "page": 3
    },
    {
      "id": "att4-medical-012",
      "phrase": "抗菌",
      "source": "附件四",
      "category": "醫療效能",
      "verdict": "forbidden",
      "star": null,
      "evidence_requirement": null,
      "raw_line": "...",
      "page": 1
    }
  ]
}
```

### 3.4 `verdict` 列舉值

| 值 | 意義 |
|---|---|
| `allowed` | 合法，無特殊佐證要求（附件二無星號） |
| `allowed_with_evidence` | 合法但需佐證（附件二有星號） |
| `conditional` | 需以成分為前提（附件三） |
| `forbidden` | 不可宣稱（附件一、附件四） |

---

## 4. 免責聲明（**每次回覆尾部固定附上，逐字使用**）

```
⚠️ 本工具僅供初步參考，不構成法律建議。
實際宣稱是否合法，需綜合整體文案、使用情境、消費者認知判斷。
最終認定以衛生福利部食品藥物管理署（TFDA）及相關主管機關為準。
如有疑慮，建議諮詢專業法遵或委任律師確認。
```

> ⚠️ **重要**：不要提及「廣告送審」。現行法規已無事前送審制度，只有事後查核。

---

## 5. Phase 0 執行任務（**Sonnet 從這裡開始動手**）

### ✅ 步驟 0.1：環境與相依

建立 `requirements.txt`：
```
pypdfium2>=4.30.0
Pillow>=10.0.0
anthropic>=0.40.0
python-telegram-bot>=21.0
python-dotenv>=1.0.0
pydantic>=2.0.0
```

先只安裝 Phase 0 需要的：`pip3 install pypdfium2 Pillow pydantic`

### ✅ 步驟 0.2：OCR 四份附件

**重要**：使用 `~/Documents/KJ-agent/shared/ocr_engine_gemini.py` 的 `extract_text_gemini()`，不要自己寫 OCR。繁體中文公文用 Gemini OCR 品質遠優於 Tesseract。

建立 `scripts/ocr_attachments.py`：
```python
#!/usr/bin/env python3
"""將 knowledge_base/raw_pdfs/ 下 4 份 PDF 透過 Gemini OCR 轉為 Markdown。"""
import sys
from pathlib import Path

# 將專案根目錄加入 path 以 import shared/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))  # → ~/Documents/KJ-agent/

from shared.ocr_engine_gemini import extract_text_gemini

RAW_DIR = PROJECT_ROOT / "knowledge_base" / "raw_pdfs"
OUT_DIR = PROJECT_ROOT / "knowledge_base" / "ocr_output"
OUT_DIR.mkdir(exist_ok=True)

for pdf in sorted(RAW_DIR.glob("*.pdf")):
    out_md = OUT_DIR / f"{pdf.stem}.md"
    if out_md.exists():
        print(f"略過已存在：{out_md.name}")
        continue
    print(f"\n▶ OCR：{pdf.name}")
    text = extract_text_gemini(pdf)
    out_md.write_text(text, encoding="utf-8")
    print(f"✔ 已寫入：{out_md}")
```

執行：
```bash
cd ~/Documents/KJ-agent/cosmetic-claim-checker
python3 scripts/ocr_attachments.py
```

預期：`knowledge_base/ocr_output/` 下產生 4 份 `.md` 檔。4 份 PDF 各 3～10 頁，約 15～40 次 API 呼叫、3～8 分鐘。

**驗收**：每份 `.md` 都有可辨識的表格或條列內容。

### ✅ 步驟 0.3：肉眼審查 OCR 品質

打開 4 份 `.md`，檢查：
- 星號標記 `*1`～`*5` 是否正確保留（OCR 容易把 `*1` 誤認為 `～1` 或 `.1`）
- 中文字是否正確（特別是「粧」不要變成「妝」）
- 表格結構是否可辨識

**若有嚴重錯字，把修正寫進對應 `.md` 檔**，別改程式。Sonnet 應該產出一份 `knowledge_base/ocr_output/REVIEW_NOTES.md` 列出所有修正點。

### ✅ 步驟 0.4：解析為結構化 JSON

建立 `scripts/build_kb.py`，分兩步：

**4a. 規則式解析（能做多少做多少）**
- 讀 `ocr_output/` 下 4 份 `.md`
- 用 regex 抽出每一行詞句 + 星號
- 依檔名判斷 `source` 與 `verdict`：
  - `附件一.md` → `forbidden`
  - `附件二.md` → `allowed` 或 `allowed_with_evidence`（視有無星號）
  - `附件三.md` → `conditional`
  - `附件四.md` → `forbidden`

**4b. LLM 輔助補全（分類欄位）**
- 對附件二，Claude API 批次呼叫，依詞句內容判斷 `category`（眼部保養、美白、保濕、抗老、清潔、防曬、頭髮護理…）
- prompt 在 `bot/prompts/categorize.md`

最終輸出：`knowledge_base/attachments.json`，格式嚴格依 §3.3。

**驗收**：
- `jq '.phrases | length' attachments.json` ≥ 100
- `jq '.phrases | group_by(.source) | map({source: .[0].source, count: length})' attachments.json` 四份附件都有筆數
- `jq '.phrases | map(select(.verdict == "allowed_with_evidence" and .star == null))' attachments.json` 回傳空陣列（有星號才能是 `allowed_with_evidence`）

### ✅ 步驟 0.5：爬取主法條文

建立 `scripts/fetch_law.py`：
- 抓 `https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099`
- 擷取法條本文（主要是條文清單）
- 存為 `knowledge_base/law_text.md`

**工具優先順序**：
1. 先試 `requests` + `beautifulsoup4` 直接爬
2. 被擋就用 `mcp__firecrawl__firecrawl_scrape`
3. 不要用 Playwright（一般網站用 Firecrawl，見專案記憶 `project_mcp_web_scraping.md`）

**驗收**：`law_text.md` 有完整條文，檔案 > 5KB。

### ✅ 步驟 0.6：同步到 Obsidian

建立 `scripts/sync_obsidian.py`：
- 目標目錄：`~/Documents/Kenji_Vault/Kenji_Vault/04_PDF_Archive/化粧品法規/`（不存在就建）
- 複製：
  - 4 份 OCR `.md`
  - `law_text.md`
  - `attachments.json`（放參考用）
- 產生一份 `INDEX.md`，列出所有檔案與更新日期
- 遵循 `shared/obsidian_writer.py` 的慣例（YAML frontmatter、不覆蓋同名檔）

**驗收**：在 Obsidian 能搜到「附件二」關鍵字。

### ✅ 步驟 0.7：建立單元測試

建立 `tests/test_kb.py`：
```python
import json
from pathlib import Path

KB = json.loads((Path(__file__).parent.parent / "knowledge_base" / "attachments.json").read_text(encoding="utf-8"))

def test_all_phrases_have_required_fields():
    for p in KB["phrases"]:
        assert all(k in p for k in ["id", "phrase", "source", "verdict"])

def test_starred_implies_allowed_with_evidence():
    for p in KB["phrases"]:
        if p.get("star"):
            assert p["verdict"] == "allowed_with_evidence"

def test_forbidden_has_no_star():
    for p in KB["phrases"]:
        if p["verdict"] == "forbidden":
            assert p.get("star") is None

def test_source_coverage():
    sources = {p["source"] for p in KB["phrases"]}
    assert sources == {"附件一", "附件二", "附件三", "附件四"}
```

執行：`python3 -m pytest tests/ -v`，全綠才算 Phase 0 完成。

---

## 6. Phase 1+ 規劃（**Phase 0 未完成前不要動這裡**）

### Phase 1：Bot MVP（純文字）
- `bot/main.py`：python-telegram-bot 進入點
- 指令：
  - `/start` — 歡迎訊息 + 免責聲明
  - `/check <文字>` — 核心查詢功能
  - 直接傳文字也視為 `/check`
- 白名單：只有 Kenji 的 Telegram user_id 可用（從 `.env` 讀 `ALLOWED_USER_IDS`）
- 回覆格式範本見 §7

### Phase 2：案例擴充機制
- `/addcase` 指令，對話式收集：宣稱文字、你的判定、理由
- 寫入 `knowledge_base/cases/YYYYMMDD_<slug>.md`
- 下次查詢時，LLM 會帶相關案例作 few-shot

### Phase 3：Fly.io 部署
- 參考 `~/Documents/KJ-agent/album-telegram-bot/fly.toml` 與 `Dockerfile`
- 東京區（`nrt`），secrets 放 `fly secrets set`

### Phase 4：圖片 OCR
- 接 `shared/ocr_engine_gemini.py` 處理圖片
- Telegram 傳圖 → OCR → 視為文字輸入

### Phase 5（遠期）：多人 UI、Web 前端

---

## 7. Bot 回覆格式範本（Phase 1 才用到，先留參考）

```markdown
🔍 *宣稱檢核結果*

📝 你查詢的宣稱：
「這條眼霜可以淡化黑眼圈」

📊 *判定：需佐證（*1 級）*

✅ 命中例示詞句：
- 「幫助/改善/淡化/調理黑眼圈」
- 出處：附件二｜眼部保養

📚 佐證強度要求：
需具備**客觀且公正試驗數據**作為佐證。
功能性較高的宣稱（粉刺、黑眼圈、改善膚質等），
主管機關通常期待**產品本身的試驗數據**作為主要佐證。

---
⚠️ 本工具僅供初步參考，不構成法律建議。
實際宣稱是否合法，需綜合整體文案、使用情境、消費者認知判斷。
最終認定以衛生福利部食品藥物管理署（TFDA）及相關主管機關為準。
如有疑慮，建議諮詢專業法遵或委任律師確認。
```

---

## 8. 環境注意事項（**Sonnet 必讀**）

### 8.1 繁體中文台灣用語（硬性要求）
- 所有輸出、回覆、註解、文件一律繁體中文
- 用台灣慣用語：**化粧品**（不是化妝品／化装品）、**程式**（不是程序）、**檔案**（不是文件）、**資料夾**（不是文件夾）
- ⚠️ 法規原文是「化**粧**品」不是「化**妝**品」，resource 名稱統一用「化粧品」

### 8.2 PDF OCR
- 一律用 `shared/ocr_engine_gemini.py` 的 `extract_text_gemini()`，不要自己包裝 Tesseract
- Gemini CLI 在 `~/.gemini/tmp/kj-agent/` 暫存圖片，處理完會自動清
- OCR 過程中 API 會消耗 Google AI Studio 免費額度（15 RPM / 1500 RPD），一次跑 4 份 PDF 沒問題

### 8.3 網路爬取
- 一般政府網站（law.moj.gov.tw）優先 `requests` + `beautifulsoup4`
- 社群媒體或需要互動才用 Playwright
- 靜態網站擋掉時改用 Firecrawl MCP（`mcp__firecrawl__firecrawl_scrape`）

### 8.4 不要做的事
- ❌ 不要 push 到 GitHub，這階段只在本地開發
- ❌ 不要 `git init`（還沒到那一步，等 Phase 1 完成再決定）
- ❌ 不要寫任何涉及廣告送審的文案（現行法規已無送審制度）
- ❌ 不要把 `ANTHROPIC_API_KEY`、`TELEGRAM_BOT_TOKEN` 寫進程式或 commit 訊息，通通 `.env`
- ❌ 不要改 `shared/` 底下的工具（共用模組，會影響其他專案）

### 8.5 建議做的事
- ✅ `.env.example` 先建好（列出所有需要的變數，值留空或用占位符）
- ✅ OCR 完成後保留 `knowledge_base/ocr_output/` 的原始 `.md`，之後 debug 用
- ✅ 每完成一個步驟跑對應驗收指令，全綠才往下走
- ✅ 遇到判斷不了的詞句分類，先標 `"category": "unknown"`，之後讓 Kenji 人工複核

---

## 9. 檔案樹（Phase 0 完成時的樣貌）

```
cosmetic-claim-checker/
├── PLAN.md                              ← 這份文件
├── README.md                            ← Phase 1 時再補
├── requirements.txt                     ← 步驟 0.1
├── .env.example                         ← 步驟 0.1
├── knowledge_base/
│   ├── raw_pdfs/                        ← 4 份原始 PDF（已就位）
│   │   ├── 附件一：涉及影響生理機能或改變身體結構之詞句.pdf
│   │   ├── 附件二：通常得使用之詞句例示或類似之詞句.pdf
│   │   ├── 附件三：成分之生理機能詞句例示或類似之詞句.pdf
│   │   └── 附件四：涉及其他醫療效能之詞句.pdf
│   ├── ocr_output/                      ← 步驟 0.2 產出
│   │   ├── 附件一....md
│   │   ├── 附件二....md
│   │   ├── 附件三....md
│   │   ├── 附件四....md
│   │   └── REVIEW_NOTES.md              ← 步驟 0.3
│   ├── law_text.md                      ← 步驟 0.5
│   ├── attachments.json                 ← 步驟 0.4（**核心產出**）
│   └── cases/                           ← Phase 2 才會有東西
├── bot/                                 ← Phase 1 才會有東西
│   └── prompts/
│       └── categorize.md                ← 步驟 0.4b
├── scripts/
│   ├── ocr_attachments.py               ← 步驟 0.2
│   ├── build_kb.py                      ← 步驟 0.4
│   ├── fetch_law.py                     ← 步驟 0.5
│   └── sync_obsidian.py                 ← 步驟 0.6
└── tests/
    └── test_kb.py                       ← 步驟 0.7
```

---

## 10. Phase 0 驗收清單（**Sonnet 完成後跑過一次**）

```bash
cd ~/Documents/KJ-agent/cosmetic-claim-checker

# 1. 4 份 OCR 都在
ls knowledge_base/ocr_output/*.md | wc -l   # 預期 ≥ 4（含 REVIEW_NOTES.md 可能 5）

# 2. 知識庫可載入
python3 -c "import json; d=json.load(open('knowledge_base/attachments.json')); print(len(d['phrases']), '筆詞句')"

# 3. 單元測試全綠
python3 -m pytest tests/ -v

# 4. 主法條文存在
test -s knowledge_base/law_text.md && echo "OK"

# 5. Obsidian 同步完成
ls ~/Documents/Kenji_Vault/Kenji_Vault/04_PDF_Archive/化粧品法規/
```

全部通過 → 回報 Kenji「Phase 0 完成」，並列出：
- 4 份附件共抽出多少筆詞句
- 各 `verdict` 類別的筆數分佈
- 有多少筆 `category == "unknown"` 需要人工複核
- OCR 過程中發現的任何文字辨識異常

然後**停下來**等 Kenji 審核，不要擅自開始 Phase 1。

---

## 11. 給接手者的最後提醒

這個專案未來會服務很多人，所以 **Phase 0 的資料品質是根基**。寧可花時間把 OCR 校對準、把 JSON schema 做對，也不要急著推進到 Bot。

如果遇到 OCR 出來的內容你看不懂法律意涵（例如某個詞句到底算合法還是越界），標 `"verdict": "needs_review"` 並在 `REVIEW_NOTES.md` 記下來，交給 Kenji 判斷。不要自己猜。

加油 💪
