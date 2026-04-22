#!/usr/bin/env python3
"""將 knowledge_base/raw_pdfs/ 下 4 份 PDF 透過 Gemini OCR 轉為 Markdown。"""
import sys
from pathlib import Path

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
