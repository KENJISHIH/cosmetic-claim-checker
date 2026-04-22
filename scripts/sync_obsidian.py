#!/usr/bin/env python3
"""
步驟 0.6：將化粧品法規知識庫同步到 Obsidian。
目標：~/Documents/Kenji_Vault/Kenji_Vault/04_PDF_Archive/化粧品法規/
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))  # → ~/Documents/KJ-agent/

VAULT_ROOT = Path.home() / "Documents" / "Kenji_Vault" / "Kenji_Vault"
TARGET_DIR = VAULT_ROOT / "04_PDF_Archive" / "化粧品法規"

OCR_DIR = PROJECT_ROOT / "knowledge_base" / "ocr_output"
KB_FILE = PROJECT_ROOT / "knowledge_base" / "attachments.json"
LAW_FILE = PROJECT_ROOT / "knowledge_base" / "law_text.md"


def safe_copy(src: Path, dst: Path) -> None:
    """複製檔案，若已存在則加時間戳後綴避免覆蓋。"""
    if dst.exists():
        suffix = datetime.now().strftime("%H%M%S")
        dst = dst.with_stem(f"{dst.stem}_{suffix}")
    shutil.copy2(src, dst)
    print(f"  ✔ 複製：{src.name} → {dst.name}")


def copy_with_frontmatter(src: Path, dst_dir: Path, category: str, tags: list[str]) -> Path:
    """
    讀取 src，加上 YAML frontmatter 後寫入 dst_dir。
    若 src 本身已有 frontmatter，附加在既有 frontmatter 之後的 content 不重複。
    """
    content = src.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    if content.startswith("---"):
        # 已有 frontmatter，直接複製
        dst = dst_dir / src.name
        if dst.exists():
            suffix = datetime.now().strftime("%H%M%S")
            dst = dst_dir / f"{src.stem}_{suffix}{src.suffix}"
        dst.write_text(content, encoding="utf-8")
    else:
        tags_str = "\n".join(f"  - {t}" for t in tags)
        frontmatter = f"""---
title: {src.stem}
date: {today}
category: {category}
tags:
{tags_str}
---

"""
        dst = dst_dir / src.name
        if dst.exists():
            suffix = datetime.now().strftime("%H%M%S")
            dst = dst_dir / f"{src.stem}_{suffix}{src.suffix}"
        dst.write_text(frontmatter + content, encoding="utf-8")

    print(f"  ✔ 同步：{src.name} → {dst.name}")
    return dst


def build_index(target_dir: Path, synced_files: list[Path]) -> None:
    """產生 INDEX.md 列出所有檔案與更新日期。"""
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "---",
        "title: 化粧品法規知識庫索引",
        f"date: {today}",
        "category: 化粧品法規",
        "tags:",
        "  - 化粧品",
        "  - 法規",
        "  - 衛福部",
        "  - TFDA",
        "---",
        "",
        "# 化粧品法規知識庫索引",
        "",
        f"> 最後更新：{now_str}",
        "",
        "## 檔案清單",
        "",
        "| 檔案 | 說明 | 大小 |",
        "|---|---|---|",
    ]

    for f in sorted(synced_files):
        size = f.stat().st_size
        desc_map = {
            "law_text.md": "主法條文 + 法律框架摘要",
            "attachments.json": "結構化詞句知識庫（241 筆）",
            "REVIEW_NOTES.md": "OCR 品質審查記錄",
        }
        desc = desc_map.get(f.name, "OCR 輸出（Markdown）")
        if "附件一" in f.name:
            desc = "附件一 OCR：禁用詞句（34 項）"
        elif "附件二" in f.name:
            desc = "附件二 OCR：合法詞句例示（6 頁）"
        elif "附件三" in f.name:
            desc = "附件三 OCR：成分型宣稱（條件式）"
        elif "附件四" in f.name:
            desc = "附件四 OCR：禁用醫療效能詞句（20 項）"
        lines.append(f"| [[{f.name}]] | {desc} | {size:,} bytes |")

    lines += [
        "",
        "## 搜尋提示",
        "",
        "- 查詢禁用詞句：搜尋「附件一」或「附件四」",
        "- 查詢合法詞句：搜尋「附件二」",
        "- 查詢成分型宣稱：搜尋「附件三」",
        "- 查詢特定功效：搜尋「保濕」、「美白」、「眼部」等關鍵字",
        "",
        "## 相關連結",
        "",
        "- 全國法規資料庫：https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099",
        "- TFDA 官網：https://www.fda.gov.tw",
    ]

    idx_file = target_dir / "INDEX.md"
    idx_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✔ 產生索引：{idx_file.name}")


def main() -> None:
    print(f"[sync_obsidian] 目標目錄：{TARGET_DIR}")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    synced: list[Path] = []

    # 同步 4 份 OCR .md（已含 HTML 注釋，加 frontmatter 後寫入）
    ocr_files = sorted(f for f in OCR_DIR.glob("*.md") if f.name != "REVIEW_NOTES.md" and "INDEX" not in f.name)
    print(f"\n同步 OCR 輸出（{len(ocr_files)} 份）：")
    for f in ocr_files:
        dst = copy_with_frontmatter(
            src=f,
            dst_dir=TARGET_DIR,
            category="化粧品法規",
            tags=["化粧品", "法規", "OCR", "附件"],
        )
        synced.append(dst)

    # 同步 REVIEW_NOTES.md
    review_src = OCR_DIR / "REVIEW_NOTES.md"
    if review_src.exists():
        print("\n同步審查記錄：")
        dst = copy_with_frontmatter(
            src=review_src,
            dst_dir=TARGET_DIR,
            category="化粧品法規",
            tags=["化粧品", "法規", "品質審查"],
        )
        synced.append(dst)

    # 同步 law_text.md
    if LAW_FILE.exists():
        print("\n同步法條文：")
        dst = copy_with_frontmatter(
            src=LAW_FILE,
            dst_dir=TARGET_DIR,
            category="化粧品法規",
            tags=["化粧品", "法規", "衛福部", "TFDA"],
        )
        synced.append(dst)

    # 同步 attachments.json（參考用）
    if KB_FILE.exists():
        print("\n同步知識庫 JSON：")
        dst_json = TARGET_DIR / "attachments.json"
        if dst_json.exists():
            suffix = datetime.now().strftime("%H%M%S")
            dst_json = TARGET_DIR / f"attachments_{suffix}.json"
        shutil.copy2(KB_FILE, dst_json)
        print(f"  ✔ 複製：{KB_FILE.name} → {dst_json.name}")
        synced.append(dst_json)

    # 產生 INDEX.md
    print("\n產生索引：")
    build_index(TARGET_DIR, synced)

    print(f"\n✔ 同步完成，共 {len(synced)} 個檔案 + INDEX.md")
    print(f"  Obsidian 路徑：{TARGET_DIR}")


if __name__ == "__main__":
    main()
