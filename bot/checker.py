#!/usr/bin/env python3
"""
bot/checker.py — 化粧品宣稱合規檢核核心邏輯
步驟：
  1. 關鍵字比對（knowledge_base/attachments.json）
  2. LLM 語意分析（Claude API）
  3. 回覆組裝（Telegram Markdown v2 格式）
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_FILE = PROJECT_ROOT / "knowledge_base" / "attachments.json"
CHECK_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "check.md"

DISCLAIMER = (
    "⚠️ 本工具僅供初步參考，不構成法律建議。\n"
    "實際宣稱是否合法，需綜合整體文案、使用情境、消費者認知判斷。\n"
    "最終認定以衛生福利部食品藥物管理署（TFDA）及相關主管機關為準。\n"
    "如有疑慮，建議諮詢專業法遵或委任律師確認。"
)

VERDICT_PRIORITY: dict[str, int] = {
    "forbidden": 4,
    "conditional": 3,
    "allowed_with_evidence": 2,
    "allowed": 1,
    "needs_review": 0,
}

VERDICT_EMOJI: dict[str, str] = {
    "forbidden": "❌",
    "conditional": "⚠️",
    "allowed_with_evidence": "📋",
    "allowed": "✅",
    "needs_review": "🔍",
}

VERDICT_LABEL: dict[str, str] = {
    "forbidden": "不可宣稱（Tier 0）",
    "conditional": "條件式合法（附件三，需成分佐證）",
    "allowed_with_evidence": "合法但需佐證",
    "allowed": "合法，無特殊佐證要求",
    "needs_review": "需進一步確認",
}

# ── 候選詞句提取 ──────────────────────────────────────────────
def _get_candidates(phrase: str) -> list[str]:
    """
    從詞句字串提取所有可能的比對候選子字串。
    處理 / ／ 、 分隔的選項 和 (括號) 選項。
    """
    candidates: set[str] = set()
    candidates.add(phrase)

    # 先以 、 切分（附件一/四的多項詞句以此分隔）
    major_sep_re = re.compile(r"[、，]")
    major_parts = major_sep_re.split(phrase)

    for major in major_parts:
        major = major.strip()
        if not major:
            continue
        # 再以 / 或 ／ 切分（選項型詞句）
        slash_parts = re.split(r"[/／]", major)
        for part in slash_parts:
            p = re.sub(r"\(.*?\)", "", part).strip()
            if len(p) >= 2:
                candidates.add(p)

        # 展開 括號 選項：消除(揮別)黑眼圈 → 消除黑眼圈 / 揮別黑眼圈
        paren_re = re.compile(r"([^\s/／]*)\(([^)]+)\)([^\s/／]*)")
        for m in paren_re.finditer(major):
            pre, alts, post = m.group(1), m.group(2), m.group(3)
            for opt in re.split(r"[/／]", alts):
                for combo in [pre + post, opt + post, pre + opt + post]:
                    c = combo.strip()
                    if len(c) >= 2:
                        candidates.add(c)

    return list(candidates)


def phrase_matches_query(phrase: str, query: str) -> bool:
    """判斷 KB 詞句是否在使用者查詢中出現。"""
    for cand in _get_candidates(phrase):
        if len(cand) >= 2 and cand in query:
            return True
    return False


# ── 資料結構 ─────────────────────────────────────────────────
@dataclass
class MatchedPhrase:
    phrase: str
    source: str
    category: str
    verdict: str
    star: str | None = None
    evidence_requirement: str | None = None


@dataclass
class CheckResult:
    query: str
    verdict: str
    matched_phrases: list[MatchedPhrase] = field(default_factory=list)
    tier_label: str = ""
    explanation: str = ""
    evidence_summary: str | None = None
    recommendation: str = ""
    needs_professional_review: bool = False
    reply_text: str = ""


# ── 主要 Checker 類別 ─────────────────────────────────────────
class CosmeticClaimChecker:
    _kb: list[dict] | None = None
    _system_prompt: str | None = None

    @property
    def kb(self) -> list[dict]:
        if self._kb is None:
            data = json.loads(KB_FILE.read_text(encoding="utf-8"))
            self._kb = data["phrases"]
        return self._kb

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = CHECK_PROMPT_FILE.read_text(encoding="utf-8")
        return self._system_prompt

    # ── 關鍵字比對 ───────────────────────────────────────────
    def keyword_match(self, query: str) -> list[MatchedPhrase]:
        matches: list[MatchedPhrase] = []
        seen_ids: set[str] = set()

        for entry in self.kb:
            pid = entry["id"]
            if pid in seen_ids:
                continue
            if phrase_matches_query(entry["phrase"], query):
                seen_ids.add(pid)
                matches.append(
                    MatchedPhrase(
                        phrase=entry["phrase"],
                        source=entry["source"],
                        category=entry.get("category", ""),
                        verdict=entry["verdict"],
                        star=entry.get("star"),
                        evidence_requirement=entry.get("evidence_requirement"),
                    )
                )

        # 依 verdict 嚴重度排序（最嚴重在前）
        matches.sort(key=lambda m: VERDICT_PRIORITY.get(m.verdict, 0), reverse=True)
        return matches

    # ── LLM 分析 ─────────────────────────────────────────────
    def llm_analyze(self, query: str, matches: list[MatchedPhrase]) -> dict:
        try:
            import anthropic
        except ImportError:
            return {"verdict": "needs_review", "explanation": "LLM 未設定", "matched_phrases": []}

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-xxx"):
            return {"verdict": "needs_review", "explanation": "ANTHROPIC_API_KEY 未設定", "matched_phrases": []}

        client = anthropic.Anthropic(api_key=api_key)
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        kb_matches_payload = [
            {
                "phrase": m.phrase,
                "source": m.source,
                "category": m.category,
                "verdict": m.verdict,
                "star": m.star,
            }
            for m in matches[:8]  # 最多傳 8 個命中詞句
        ]

        user_msg = json.dumps(
            {
                "query": query,
                "kb_matches": kb_matches_payload,
                "law_context": (
                    "依「化粧品標示宣傳廣告涉及虛偽誇大或醫療效能認定準則」（L0030099）判定。"
                    "附件一、四為禁用詞句；附件二為合法詞句（部分需星號等級佐證）；"
                    "附件三為成分型條件式宣稱。整體應依消費者認知綜合判斷。"
                ),
            },
            ensure_ascii=False,
        )

        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text.strip()
        # 清除可能的 markdown 程式碼區塊
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)

    # ── 整體判定 ─────────────────────────────────────────────
    def _merge_verdict(
        self, keyword_matches: list[MatchedPhrase], llm_data: dict
    ) -> str:
        """優先採用關鍵字比對結果；若無命中，採用 LLM 結果。"""
        if keyword_matches:
            top = keyword_matches[0].verdict
            # LLM 可以將 verdict 升級（更嚴格），但不降級
            llm_verdict = llm_data.get("verdict", "needs_review")
            if VERDICT_PRIORITY.get(llm_verdict, 0) > VERDICT_PRIORITY.get(top, 0):
                return llm_verdict
            return top
        return llm_data.get("verdict", "needs_review")

    # ── 回覆組裝 ─────────────────────────────────────────────
    def _format_reply(self, result: CheckResult) -> str:
        emoji = VERDICT_EMOJI.get(result.verdict, "❓")
        label = VERDICT_LABEL.get(result.verdict, result.verdict)

        lines: list[str] = [
            "🔍 *宣稱檢核結果*",
            "",
            f'📝 你查詢的宣稱：\n「{result.query}」',
            "",
            f"📊 *判定：{emoji} {label}*",
            "",
        ]

        # 命中詞句
        if result.matched_phrases:
            header_map = {
                "forbidden": "🚫 命中禁用詞句：",
                "conditional": "⚠️ 命中條件式宣稱（附件三）：",
                "allowed_with_evidence": "📋 命中需佐證詞句：",
                "allowed": "✅ 命中合法詞句：",
            }
            # 分組顯示（最多 5 個）
            shown: set[str] = set()
            for m in result.matched_phrases[:5]:
                if m.phrase in shown:
                    continue
                shown.add(m.phrase)
                hdr = header_map.get(m.verdict, "📌 命中詞句：")
                if hdr not in lines:
                    lines.append(hdr)
                star_txt = f"（需佐證 {m.star}）" if m.star else ""
                lines.append(f"- 「{m.phrase}」{star_txt}")
                lines.append(f"  出處：{m.source}｜{m.category}")
            lines.append("")

        # 佐證需求
        if result.evidence_summary:
            lines += ["📚 *佐證強度要求：*", result.evidence_summary, ""]

        # LLM 解釋
        if result.explanation and result.explanation != "LLM 未設定":
            lines += ["💬 *分析說明：*", result.explanation, ""]

        # 建議
        if result.recommendation:
            lines += ["💡 *建議：*", result.recommendation, ""]

        # 免責聲明
        lines += ["---", DISCLAIMER]

        return "\n".join(lines)

    # ── 主要入口 ─────────────────────────────────────────────
    def check(self, query: str) -> CheckResult:
        query = query.strip()
        if not query:
            raise ValueError("查詢文字不得為空")

        # Step 1: 關鍵字比對
        kw_matches = self.keyword_match(query)

        # Step 2: LLM 分析（補全說明文字）
        try:
            llm_data = self.llm_analyze(query, kw_matches)
        except Exception as e:
            llm_data = {
                "verdict": kw_matches[0].verdict if kw_matches else "needs_review",
                "explanation": f"LLM 分析暫時無法取得：{e}",
                "matched_phrases": [],
                "evidence_summary": None,
                "recommendation": "",
                "needs_professional_review": True,
            }

        # Step 3: 整合 verdict
        verdict = self._merge_verdict(kw_matches, llm_data)

        # 合併 LLM 回傳的額外命中詞句
        llm_matches_raw = llm_data.get("matched_phrases", [])
        all_phrases = list(kw_matches)
        seen_phrases = {m.phrase for m in kw_matches}
        for lm in llm_matches_raw:
            if lm.get("phrase") and lm["phrase"] not in seen_phrases:
                all_phrases.append(
                    MatchedPhrase(
                        phrase=lm["phrase"],
                        source=lm.get("source", ""),
                        category=lm.get("category", ""),
                        verdict=lm.get("verdict", verdict),
                        star=lm.get("star"),
                    )
                )
                seen_phrases.add(lm["phrase"])

        result = CheckResult(
            query=query,
            verdict=verdict,
            matched_phrases=all_phrases,
            tier_label=llm_data.get("tier_label", VERDICT_LABEL.get(verdict, "")),
            explanation=llm_data.get("explanation", ""),
            evidence_summary=llm_data.get("evidence_summary"),
            recommendation=llm_data.get("recommendation", ""),
            needs_professional_review=llm_data.get("needs_professional_review", False),
        )
        result.reply_text = self._format_reply(result)
        return result


# ── Singleton ─────────────────────────────────────────────────
_checker: CosmeticClaimChecker | None = None


def get_checker() -> CosmeticClaimChecker:
    global _checker
    if _checker is None:
        _checker = CosmeticClaimChecker()
    return _checker
