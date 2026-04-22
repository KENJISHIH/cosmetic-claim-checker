#!/usr/bin/env python3
"""
步驟 0.4：解析 OCR Markdown → knowledge_base/attachments.json
  4a. regex 抽取詞句 + 星號
  4b. Claude API 補全 category（附件二）
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OCR_DIR = PROJECT_ROOT / "knowledge_base" / "ocr_output"
KB_FILE = PROJECT_ROOT / "knowledge_base" / "attachments.json"
PROMPT_FILE = PROJECT_ROOT / "bot" / "prompts" / "categorize.md"

# ── 星號說明 ──────────────────────────────────────────────────
STAR_REQUIREMENTS: dict[str, str] = {
    "*1": "須具備客觀且公正試驗數據佐證",
    "*2": "須符合化粧品產品資訊檔案管理辦法規定，含客觀且公正科學性佐證或其他足以證明功效者",
    "*3": "成分經有機驗證機構驗證，並提出證明文件",
    "*4": "天然成分直接來自植物/動物/礦物，未添加非天然成分，或符合ISO規範並提出證明文件",
    "*5": "產品通過有機/天然驗證機構驗證並取得標章，並提出有關證明文件",
}

STAR_RE = re.compile(r"\*\d")


def extract_stars(text: str) -> tuple[str, str | None]:
    stars = STAR_RE.findall(text)
    if stars:
        # 去重複，保留出現順序（同一項目多個子詞句可能重複標注同一星號）
        seen: set[str] = set()
        unique: list[str] = []
        for s in stars:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        clean = STAR_RE.sub("", text).strip().rstrip("、").strip()
        return clean, "".join(unique)
    return text.strip(), None


def star_to_requirement(star: str | None) -> str | None:
    if not star:
        return None
    parts = STAR_RE.findall(star)
    reqs = [STAR_REQUIREMENTS[p] for p in parts if p in STAR_REQUIREMENTS]
    return "；".join(reqs) if reqs else None


# ── 附件一 / 附件四 — 簡單數字列表 ──────────────────────────
def parse_forbidden_list(text: str, source: str) -> list[dict]:
    prefix = "att1" if source == "附件一" else "att4"
    category = "影響生理機能或身體結構" if source == "附件一" else "醫療效能"
    phrases = []
    page = 1
    for line in text.split("\n"):
        pg = re.match(r"<!--\s*第\s*(\d+)\s*頁\s*-->", line)
        if pg:
            page = int(pg.group(1))
            continue
        m = re.match(r"^(\d+)\.\s+(.+)", line.strip())
        if not m:
            continue
        item_no = int(m.group(1))
        raw = m.group(2).strip()
        if "其他類似" in raw:
            continue
        phrase, _ = extract_stars(raw)  # forbidden 的 *1 只是過渡期，不影響判定
        phrases.append(
            {
                "id": f"{prefix}-{item_no:03d}",
                "phrase": phrase,
                "source": source,
                "category": category,
                "verdict": "forbidden",
                "star": None,
                "evidence_requirement": None,
                "raw_line": line.strip(),
                "page": page,
            }
        )
    return phrases


# ── 附件三 — 表格結構、成分型宣稱 ───────────────────────────
def parse_att3(text: str) -> list[dict]:
    phrases = []
    n = 0
    page = 1
    for line in text.split("\n"):
        pg = re.match(r"<!--\s*第\s*(\d+)\s*頁\s*-->", line)
        if pg:
            page = int(pg.group(1))
            continue
        if re.match(r"^\s*\|[-:| ]+\|\s*$", line):
            continue
        # 移除 markdown table 語法，提取 cell 內容
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            content = " ".join(cells)
        else:
            content = line.strip()

        # 處理 <br> 分隔的多項目
        for sub in re.split(r"<br\s*/?>", content):
            sub = sub.strip()
            m = re.match(r"^(\d+)\.\s+(.+)", sub)
            if not m:
                continue
            raw = m.group(2).strip()
            if "其他類似" in raw:
                continue
            phrase, star = extract_stars(raw)
            n += 1
            phrases.append(
                {
                    "id": f"att3-{n:03d}",
                    "phrase": phrase,
                    "source": "附件三",
                    "category": "成分型宣稱（牙膏漱口水）",
                    "verdict": "conditional",
                    "star": star,
                    "evidence_requirement": (
                        "須以特定成分（如氟化物、檸檬酸鉀等）為前提，並配合正確刷牙習慣宣稱"
                    ),
                    "raw_line": sub,
                    "page": page,
                }
            )
    return phrases


# ── 附件二 — 複雜多類別格式 ─────────────────────────────────
CHINESE_NUM: dict[str, int] = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
}

ATT2_CATEGORY_MAP: dict[int, str] = {
    1: "洗髮",
    2: "洗臉卸粧",
    3: "沐浴",
    4: "香皂",
    5: "頭髮護理",
    6: "保養（化妝水/面霜乳液）",
    7: "香氛",
    8: "止汗制臭",
    9: "唇部",
    10: "彩妝（覆敷）",
    11: "眼部",
    12: "指甲",
    13: "牙齒美白",
    14: "口腔衛生（牙膏漱口水）",
    15: "通則",
}

# 匹配中文數字序號（一、到十五、）
_CH_NUM_PATT = "|".join(
    re.escape(k) for k in sorted(CHINESE_NUM.keys(), key=len, reverse=True)
)
CATEGORY_HDR_RE = re.compile(rf"^(?:{_CH_NUM_PATT})、")


def _parse_chinese_num(s: str) -> int | None:
    """從字串起首解析中文數字，回傳整數或 None。"""
    for ch in sorted(CHINESE_NUM.keys(), key=len, reverse=True):
        if s.startswith(ch + "、"):
            return CHINESE_NUM[ch]
    return None


def parse_att2(text: str) -> list[dict]:
    # 移除 HTML 注釋
    text = re.sub(r"<!--.*?-->", "", text)

    current_cat_no: int | None = None
    current_cat_name = "unknown"
    n = 0  # global counter
    phrases: list[dict] = []
    page = 1

    def make_entry(phrase: str, star: str | None, raw: str) -> dict | None:
        nonlocal n
        if not phrase or len(phrase) < 2:
            return None
        if "其他類似" in phrase:
            return None
        verdict = "allowed_with_evidence" if star else "allowed"
        n += 1
        return {
            "id": f"att2-{n:03d}",
            "phrase": phrase,
            "source": "附件二",
            "category": current_cat_name,
            "verdict": verdict,
            "star": star,
            "evidence_requirement": star_to_requirement(star),
            "raw_line": raw,
            "page": page,
        }

    def process_item_text(raw: str, raw_line: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        phrase, star = extract_stars(raw)
        entry = make_entry(phrase, star, raw_line)
        if entry:
            phrases.append(entry)

    for line in text.split("\n"):
        # 頁碼行
        if re.match(r"^\d+\s*$", line.strip()):
            try:
                page = int(line.strip())
            except ValueError:
                pass
            continue

        # markdown 表格分隔行
        if re.match(r"^\s*\|[-:| ]+\|\s*$", line):
            continue

        # Markdown 表格行
        if "|" in line:
            # 分割 cells（保留空 cell 結構）
            raw_cells = line.split("|")
            # 移除首尾空字串（由 | 分隔導致）
            if raw_cells and raw_cells[0].strip() == "":
                raw_cells = raw_cells[1:]
            if raw_cells and raw_cells[-1].strip() == "":
                raw_cells = raw_cells[:-1]

            cells = [c.strip() for c in raw_cells]

            # 嘗試從第一欄偵測類別
            if cells:
                first = cells[0]
                cat_no = _parse_chinese_num(first)
                if cat_no:
                    current_cat_no = cat_no
                    current_cat_name = ATT2_CATEGORY_MAP.get(cat_no, "unknown")

            # 從所有 cell 中提取編號項目
            for cell in cells:
                for sub in re.split(r"<br\s*/?>", cell):
                    sub = sub.strip()
                    m = re.match(r"^(\d+)\.\s+(.+)", sub)
                    if m:
                        process_item_text(m.group(2), sub)
            continue

        # 一般行
        line_s = line.strip()
        if not line_s:
            continue

        # 類別標題行（含中文數字 + 、）
        cat_no = _parse_chinese_num(line_s)
        if cat_no:
            current_cat_no = cat_no
            current_cat_name = ATT2_CATEGORY_MAP.get(cat_no, "unknown")
            continue

        # 編號項目行
        m = re.match(r"^(\d+)\.\s+(.+)", line_s)
        if m:
            process_item_text(m.group(2), line_s)

    return phrases


# ── Claude API 補全 category（步驟 4b）─────────────────────
def refine_categories_with_llm(att2_phrases: list[dict]) -> list[dict]:
    """
    對附件二的 phrases，批次呼叫 Claude API 改善 category 標籤。
    使用 bot/prompts/categorize.md 作為 system prompt。
    """
    try:
        import anthropic
    except ImportError:
        print("⚠ anthropic 未安裝，跳過 LLM 分類（category 維持文件結構分類）")
        return att2_phrases

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-xxx"):
        print("⚠ ANTHROPIC_API_KEY 未設定，跳過 LLM 分類（category 維持文件結構分類）")
        return att2_phrases

    print(f"\n[LLM 分類] 開始批次分類 {len(att2_phrases)} 筆附件二詞句...")
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")
    client = anthropic.Anthropic(api_key=api_key)

    # 批次大小：每次最多 50 筆
    BATCH = 50
    id_to_phrase = {p["id"]: p for p in att2_phrases}

    for start in range(0, len(att2_phrases), BATCH):
        batch = att2_phrases[start : start + BATCH]
        payload = [{"id": p["id"], "phrase": p["phrase"]} for p in batch]
        user_msg = json.dumps(payload, ensure_ascii=False)

        try:
            resp = client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = resp.content[0].text.strip()
            # 清除可能的 markdown 程式碼區塊
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            results = json.loads(raw)
            for item in results:
                pid = item.get("id")
                cat = item.get("category", "unknown")
                if pid in id_to_phrase:
                    id_to_phrase[pid]["category"] = cat
            print(f"  [LLM 分類] 批次 {start//BATCH + 1} 完成（{len(batch)} 筆）")
        except Exception as e:
            print(f"  [LLM 分類] ✗ 批次 {start//BATCH + 1} 失敗：{e}")

    return att2_phrases


# ── 組裝 metadata ────────────────────────────────────────────
def build_metadata() -> dict:
    return {
        "source_law": "化粧品衛生安全管理法 / 化粧品之標示宣傳廣告涉及虛偽誇大或醫療效能認定準則",
        "law_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099",
        "last_updated": "2026-04-22",
        "star_notes": {
            "*1": "須具備客觀且公正試驗數據佐證",
            "*2": "須符合化粧品產品資訊檔案管理辦法規定，含客觀且公正科學性佐證或其他足以證明功效者",
            "*3": "成分經有機驗證機構驗證，並提出證明文件",
            "*4": "天然成分直接來自植物/動物/礦物，未添加非天然成分，或符合ISO規範並提出證明文件",
            "*5": "產品通過有機/天然驗證機構驗證並取得標章，並提出有關證明文件",
        },
    }


# ── 主程式 ────────────────────────────────────────────────────
def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

    phrases: list[dict] = []

    # 4a 規則式解析
    for stem, source in [
        ("附件一：涉及影響生理機能或改變身體結構之詞句", "附件一"),
        ("附件四：涉及其他醫療效能之詞句", "附件四"),
    ]:
        path = OCR_DIR / f"{stem}.md"
        print(f"\n[解析] {source}：{path.name}")
        text = path.read_text(encoding="utf-8")
        result = parse_forbidden_list(text, source)
        print(f"  → {len(result)} 筆")
        phrases.extend(result)

    # 附件三
    path3 = OCR_DIR / "附件三：成分之生理機能詞句例示或類似之詞句.md"
    print(f"\n[解析] 附件三：{path3.name}")
    text3 = path3.read_text(encoding="utf-8")
    att3 = parse_att3(text3)
    print(f"  → {len(att3)} 筆")
    phrases.extend(att3)

    # 附件二
    path2 = OCR_DIR / "附件二：通常得使用之詞句例示或類似之詞句.md"
    print(f"\n[解析] 附件二：{path2.name}")
    text2 = path2.read_text(encoding="utf-8")
    att2 = parse_att2(text2)
    print(f"  → {len(att2)} 筆（初始類別依文件結構）")

    # 4b LLM 補全分類
    att2 = refine_categories_with_llm(att2)
    phrases.extend(att2)

    # 輸出統計
    print(f"\n[統計] 共 {len(phrases)} 筆詞句")
    by_source: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    unknown_count = 0
    for p in phrases:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
        by_verdict[p["verdict"]] = by_verdict.get(p["verdict"], 0) + 1
        if p.get("category") == "unknown":
            unknown_count += 1
    for src, cnt in sorted(by_source.items()):
        print(f"  {src}: {cnt} 筆")
    for verd, cnt in sorted(by_verdict.items()):
        print(f"  verdict={verd}: {cnt} 筆")
    print(f"  category=unknown: {unknown_count} 筆（需人工複核）")

    # 寫出 JSON
    output = {"metadata": build_metadata(), "phrases": phrases}
    KB_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✔ 已寫入：{KB_FILE}（{KB_FILE.stat().st_size:,} bytes）")


if __name__ == "__main__":
    main()
