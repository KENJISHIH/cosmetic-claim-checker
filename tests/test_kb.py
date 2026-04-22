import json
from pathlib import Path

KB = json.loads(
    (Path(__file__).parent.parent / "knowledge_base" / "attachments.json").read_text(
        encoding="utf-8"
    )
)


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


def test_minimum_phrase_count():
    assert len(KB["phrases"]) >= 100


def test_metadata_has_star_notes():
    meta = KB["metadata"]
    assert "star_notes" in meta
    assert all(k in meta["star_notes"] for k in ["*1", "*2", "*3", "*4", "*5"])


def test_no_empty_phrases():
    for p in KB["phrases"]:
        assert p["phrase"].strip(), f"id={p['id']} 的 phrase 為空字串"


def test_verdict_values_are_valid():
    valid = {"allowed", "allowed_with_evidence", "conditional", "forbidden"}
    for p in KB["phrases"]:
        assert p["verdict"] in valid, f"id={p['id']} 的 verdict 值無效：{p['verdict']}"


def test_conditional_from_att3_only():
    for p in KB["phrases"]:
        if p["verdict"] == "conditional":
            assert p["source"] == "附件三", (
                f"id={p['id']} verdict=conditional 但 source={p['source']}（應只有附件三）"
            )


def test_forbidden_sources_are_att1_att4():
    for p in KB["phrases"]:
        if p["verdict"] == "forbidden":
            assert p["source"] in {"附件一", "附件四"}, (
                f"id={p['id']} verdict=forbidden 但 source={p['source']}"
            )


def test_ids_are_unique():
    ids = [p["id"] for p in KB["phrases"]]
    assert len(ids) == len(set(ids)), "存在重複的 id"
