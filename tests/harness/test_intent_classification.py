# [阶段1] IntentClassification 解析与归一化

from app.harness.planning.gateway import _parse_classification
from app.harness.types.intent import IntentClassification


def test_parse_valid_json():
    raw = '{"mode": "smart_query", "confidence": 0.9, "reasoning": "查销售额"}'
    r = _parse_classification(raw)
    assert r.mode == "smart_query"
    assert r.confidence == 0.9
    assert r.reasoning == "查销售额"


def test_parse_invalid_mode_falls_back_chitchat():
    raw = '{"mode": "unknown", "confidence": 0.8, "reasoning": "x"}'
    r = _parse_classification(raw)
    assert r.mode == "chitchat"
    assert r.confidence <= 0.5


def test_fallback_unparsed():
    r = _parse_classification("not json at all")
    assert r.mode == "chitchat"
    assert r.confidence == 0.3


def test_normalize_clamps_confidence():
    r = IntentClassification.normalize(mode="report", confidence=1.5, reasoning="")
    assert r.confidence == 1.0
