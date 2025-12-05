import pytest

webrtcvad = pytest.importorskip("webrtcvad")
from backend.services.dictation.silence_gate import SilenceGate
from backend.services.dictation.repeat_filter import suppress_repeated_ngrams


def test_dictation_long_pause_e2e():
    vad = webrtcvad.Vad(1)
    gate = SilenceGate(vad, threshold_ms=60, frame_ms=20)
    frame = b"\x00" * (2 * 16000 * gate.frame_ms // 1000)
    gate.update(frame, 16000)
    gate.update(frame, 16000)
    assert gate.update(frame, 16000)
    raw = "we meet again we meet again"
    assert suppress_repeated_ngrams(raw, n=3) == "we meet again"
"""NOTE: moved under tests/dictation by dictation_tests_reorg"""
