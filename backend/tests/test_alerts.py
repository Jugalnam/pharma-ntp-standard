"""경고 판정 단위 테스트 — RISK-001(High) 완화, OQ-022a/b 대응.

경계값(한계 ±1)을 명시적으로 검증한다.
"""
import pytest

from app.services.alerts import is_offset_breach


@pytest.mark.parametrize(
    "offset_ms, max_offset_ms, expected",
    [
        (999.0, 1000.0, False),    # 한계 이내 (OQ-022a)
        (1000.0, 1000.0, False),   # 정확히 한계 → 합격
        (1000.1, 1000.0, True),    # 한계 초과 (OQ-022b)
        (-1000.1, 1000.0, True),   # 음수 오프셋도 절댓값으로 판정
        (0.0, 1000.0, False),
        (5000.0, 1000.0, True),
    ],
)
def test_is_offset_breach(offset_ms, max_offset_ms, expected):
    assert is_offset_breach(offset_ms, max_offset_ms) is expected


def test_negative_limit_rejected():
    with pytest.raises(ValueError):
        is_offset_breach(0.0, -1.0)
