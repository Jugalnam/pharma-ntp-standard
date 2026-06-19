"""오프셋 경고 판정 로직.

[RISK-001] (RPN=18, High): 오프셋 한계 초과를 경고하지 못하면 잘못된
타임스탬프가 GxP 기록에 유입될 수 있다. 본 모듈은 위험 완화의 핵심이며
경계값을 포함한 단위 테스트(OQ-022a/b 대응)로 검증한다.
"""


def is_offset_breach(offset_ms: float, max_offset_ms: float) -> bool:
    """측정 오프셋의 절댓값이 허용 한계를 초과하면 True(경고).

    경계 정의: 오프셋 절댓값이 한계와 '같으면' 합격(경고 아님),
    한계를 '초과'할 때만 경고한다.

    >>> is_offset_breach(999, 1000)
    False
    >>> is_offset_breach(1000, 1000)
    False
    >>> is_offset_breach(1001, 1000)
    True
    >>> is_offset_breach(-1001, 1000)
    True
    """
    if max_offset_ms < 0:
        raise ValueError("max_offset_ms must be non-negative")
    return abs(offset_ms) > max_offset_ms
