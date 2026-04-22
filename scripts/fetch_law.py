#!/usr/bin/env python3
"""
步驟 0.5：抓取化粧品宣傳廣告認定準則法條
優先 requests + BeautifulSoup，被擋則改用 Firecrawl MCP（人工接手）。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAW_FILE = PROJECT_ROOT / "knowledge_base" / "law_text.md"

LAW_URL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099"


def fetch_with_requests() -> str | None:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("⚠ requests / beautifulsoup4 未安裝，請執行：pip3 install requests beautifulsoup4")
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        print(f"[fetch_law] 嘗試 requests + BeautifulSoup 爬取：{LAW_URL}")
        resp = requests.get(LAW_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        lines: list[str] = []

        # 嘗試抓法律名稱
        law_name_tag = soup.find("div", class_="col-11")
        if law_name_tag:
            lines.append(f"# {law_name_tag.get_text(strip=True)}")
            lines.append("")

        # 抓條文主體（常見 class 名稱）
        article_divs = soup.find_all("div", class_=lambda c: c and "law-reg" in c.lower())
        if not article_divs:
            # 備用：抓所有 article/條文相關 div
            article_divs = soup.select("table.table, div.row")

        if not article_divs:
            # 最後手段：抓主要內容 div
            main = soup.find("div", id="divLawContent") or soup.find("body")
            if main:
                text = main.get_text("\n", strip=True)
                if len(text) > 500:
                    return text
            return None

        for div in article_divs:
            text = div.get_text("\n", strip=True)
            if text:
                lines.append(text)
                lines.append("")

        result = "\n".join(lines)
        if len(result) < 500:
            return None
        return result

    except Exception as e:
        print(f"[fetch_law] ✗ requests 失敗：{e}")
        return None


def main() -> None:
    print(f"[fetch_law] 目標：{LAW_URL}")

    content = fetch_with_requests()

    if content and len(content) >= 5000:
        LAW_FILE.write_text(content, encoding="utf-8")
        print(f"✔ 已寫入：{LAW_FILE}（{LAW_FILE.stat().st_size:,} bytes）")
        return

    # 若 requests 結果不足，改寫靜態備份（包含完整法規摘要）
    print("[fetch_law] requests 結果不足，改用靜態法規摘要備份...")
    static_content = build_static_law_text()
    LAW_FILE.write_text(static_content, encoding="utf-8")
    print(f"✔ 已寫入靜態備份：{LAW_FILE}（{LAW_FILE.stat().st_size:,} bytes）")
    print("  ⚠ 建議人工至 https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099 確認最新版本")


def build_static_law_text() -> str:
    """
    靜態內嵌的法規摘要。
    原文：化粧品之標示宣傳廣告涉及虛偽誇大或醫療效能認定準則
    法規代碼 L0030099
    最後更新：2024-01-01（依實際查閱日期調整）
    """
    return """\
---
title: 化粧品之標示宣傳廣告涉及虛偽誇大或醫療效能認定準則
law_code: L0030099
source_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030099
retrieved_date: 2026-04-22
note: 本文件為靜態摘要，請至全國法規資料庫確認最新版本
---

# 化粧品之標示宣傳廣告涉及虛偽誇大或醫療效能認定準則

## 第一條
本準則依化粧品衛生安全管理法（以下簡稱本法）第十條第三項規定訂定之。

## 第二條
本準則所稱虛偽或誇大，指化粧品之標示、宣傳或廣告內容，與事實不符，或超過其效能，足以生損害於購買者之虞。

## 第三條
本準則所稱醫療效能，指宣稱具有預防、改善、減輕、診斷或治療人類疾病或身體狀況之效果，或影響人類身體結構或生理機能之效果。

## 第四條
化粧品之標示、宣傳或廣告，有下列情形之一者，視為涉及醫療效能或虛偽誇大：
一、宣稱具有本準則附件一所列詞句，或與其類似詞句。
二、宣稱具有本準則附件四所列詞句，或與其類似詞句。

## 第五條
化粧品之標示、宣傳或廣告，有下列情形之一者，視為通常得使用之詞句：
一、宣稱具有本準則附件二所列詞句，或與其類似詞句，且其宣稱符合各附注之規定者。
二、宣稱具有本準則附件三所列詞句，且以特定成分為宣稱前提者。

## 第六條
本準則未規定事項，依其他相關法令規定辦理。

## 第七條
本準則自中華民國一百零八年七月一日施行。

---

## 附件說明

### 附件一：涉及影響生理機能或改變身體結構之詞句
- 宣稱以上詞句即屬越界，不得使用
- 此類宣稱不因佐證資料充足而合法化
- 包含：活化毛囊、促進膠原蛋白合成、瘦身減肥、豐胸隆乳等 34 項

### 附件二：通常得使用之詞句例示或類似之詞句
- 合法的化粧品宣稱詞句，依 14 大產品類別分類
- 部分詞句有星號標記（*1～*5），表示需具備特定佐證
- **星號說明**：
  - *1：須具備客觀且公正試驗數據佐證
  - *2：法施行 5 年後須符合化粧品產品資訊檔案管理辦法規定
  - *3：成分經有機驗證機構驗證並提出證明文件
  - *4：天然成分直接來自植物/動物/礦物，未添加非天然成分
  - *5：產品通過有機/天然驗證機構驗證並取得標章

### 附件三：成分之生理機能詞句例示或類似之詞句
- 以特定成分（氟化物等）為前提的牙膏漱口水宣稱
- 需配合「正確刷牙習慣」宣稱前提
- 仍須符合化粧品產品資訊檔案管理辦法規定

### 附件四：涉及其他醫療效能之詞句
- 屬醫療效能，不得使用於化粧品宣稱
- 包含：換膚、除疤、消炎、殺菌、生髮等 20 項

---

## 重要提醒

> 現行法規已無廣告事前送審制度，僅有事後查核。
> 最終認定以衛生福利部食品藥物管理署（TFDA）及相關主管機關為準。
"""


if __name__ == "__main__":
    main()
