"""
tests/test_checker.py — 關鍵字比對邏輯單元測試（不呼叫 LLM）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.checker import CosmeticClaimChecker, _get_candidates, phrase_matches_query

checker = CosmeticClaimChecker()


# ── _get_candidates 展開測試 ─────────────────────────────────
def test_candidates_slash():
    cands = _get_candidates("幫助/改善/淡化黑眼圈")
    assert "幫助" in cands
    assert "改善" in cands
    assert "淡化黑眼圈" in cands


def test_candidates_ideographic_comma():
    cands = _get_candidates("消炎、抑炎、退紅腫")
    assert "消炎" in cands
    assert "抑炎" in cands
    assert "退紅腫" in cands


def test_candidates_parenthetical():
    cands = _get_candidates("消除(揮別)黑眼圈")
    assert "消除黑眼圈" in cands
    assert "揮別黑眼圈" in cands


def test_candidates_complex():
    cands = _get_candidates("促進(刺激)膠原蛋白合成、促進(刺激)膠原蛋白增生")
    assert "促進膠原蛋白合成" in cands
    assert "刺激膠原蛋白合成" in cands


# ── phrase_matches_query 比對測試 ────────────────────────────
def test_match_forbidden_collagen():
    assert phrase_matches_query(
        "促進(刺激)膠原蛋白合成、促進(刺激)膠原蛋白增生",
        "促進膠原蛋白合成",
    )


def test_match_forbidden_collagen_negative():
    assert not phrase_matches_query(
        "促進(刺激)膠原蛋白合成、促進(刺激)膠原蛋白增生",
        "補充玻尿酸",
    )


def test_match_wrinkle_forbidden():
    assert phrase_matches_query(
        "皺紋填補、消除皺紋、消除細紋、消除表情紋、消除法令紋、消除魚尾紋、消除伸展紋",
        "消除皺紋",
    )


def test_match_black_eye_circle():
    assert phrase_matches_query(
        "幫助/改善/淡化/調理黑眼圈、幫助/改善/淡化/調理熊貓眼、幫助/改善/淡化/調理泡泡眼",
        "淡化黑眼圈",
    )


def test_no_match_short_string():
    assert not phrase_matches_query("消炎", "消費")


# ── keyword_match 整體邏輯 ───────────────────────────────────
def test_forbidden_takes_priority():
    """禁用詞句排序應在合法詞句之前。"""
    matches = checker.keyword_match("消除皺紋")
    assert matches, "應有命中"
    assert matches[0].verdict == "forbidden"


def test_black_eye_circle_needs_evidence():
    matches = checker.keyword_match("淡化黑眼圈")
    assert matches
    assert any(m.verdict == "allowed_with_evidence" for m in matches)
    assert matches[0].verdict == "allowed_with_evidence"


def test_forbidden_collagen():
    matches = checker.keyword_match("促進膠原蛋白合成")
    assert matches
    assert matches[0].verdict == "forbidden"


def test_forbidden_anti_inflammation():
    matches = checker.keyword_match("消炎殺菌")
    assert matches
    assert matches[0].verdict == "forbidden"


def test_allowed_herbal():
    matches = checker.keyword_match("草本植萃")
    assert matches
    assert matches[0].verdict == "allowed"


def test_no_match_unrelated():
    matches = checker.keyword_match("這個產品很好用")
    assert len(matches) == 0


def test_forbidden_slimming():
    matches = checker.keyword_match("瘦身減肥")
    assert matches
    assert matches[0].verdict == "forbidden"
