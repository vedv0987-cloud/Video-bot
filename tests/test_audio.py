from __future__ import annotations

import pytest

from videobot.audio.align import EstimatedAligner, WhisperXAligner, get_aligner
from videobot.audio.beats import FixedTempoBeats, LibrosaBeats, get_beat_source
from videobot.audio.speech import BackendUnavailable, NullSpeech, get_speech_backend, wav_duration

SECTIONS = [
    {"id": "hook", "text": "Here is what the evidence says.", "items": []},
    {"id": "point-1", "text": "Water regulates body temperature.", "items": ["Every cell needs it."]},
]


# --- speech ---------------------------------------------------------------


def test_null_speech_writes_a_readable_wav(tmp_path):
    backend = NullSpeech()
    text = "one two three four five six seven eight nine ten"
    path = tmp_path / "vo.wav"
    path.write_bytes(backend.synthesize(text))

    assert wav_duration(path) == pytest.approx(backend.estimate_duration(text), abs=0.01)


def test_null_speech_is_never_zero_length():
    assert NullSpeech().estimate_duration("hi") >= 1.0


@pytest.mark.parametrize("name", ["kokoro", "chatterbox"])
def test_real_backends_fail_with_an_install_hint(name):
    """A missing model must say how to get it, not raise ImportError."""
    with pytest.raises(BackendUnavailable, match="Install it with"):
        get_speech_backend(name).synthesize("hello")


def test_unknown_speech_backend_is_rejected():
    with pytest.raises(KeyError, match="unknown speech backend"):
        get_speech_backend("elevenlabs")


# --- alignment ------------------------------------------------------------


def test_estimated_alignment_covers_every_word_in_order():
    result = EstimatedAligner().align(SECTIONS, 10.0)

    assert [w["w"] for w in result.words][:3] == ["Here", "is", "what"]
    assert len(result.words) == 14  # 6 + 4 + 4 across both sections
    assert all(a["t1"] <= b["t0"] for a, b in zip(result.words, result.words[1:]))
    assert result.words[-1]["t1"] <= 10.0
    assert result.method == "estimated"


def test_estimated_alignment_gives_longer_words_more_time():
    """A flat split makes every caption window equal, which reads visibly wrong."""
    words = {w["w"]: w["t1"] - w["t0"] for w in EstimatedAligner().align(SECTIONS, 10.0).words}
    assert words["temperature."] > words["is"]


def test_alignment_reports_a_span_per_section():
    result = EstimatedAligner().align(SECTIONS, 10.0)
    assert [s["id"] for s in result.sections] == ["hook", "point-1"]
    assert result.sections[0]["t1"] <= result.sections[1]["t0"]


def test_alignment_of_nothing_is_empty():
    assert EstimatedAligner().align([], 5.0).words == []


def test_whisperx_is_not_installed_here():
    with pytest.raises(BackendUnavailable, match="whisperx"):
        WhisperXAligner().align(SECTIONS, 10.0)


def test_unknown_aligner_is_rejected():
    with pytest.raises(KeyError, match="unknown aligner"):
        get_aligner("nope")


# --- beats ----------------------------------------------------------------


def test_fixed_tempo_lays_an_even_grid():
    beat_map = FixedTempoBeats(120).beats(4.0)
    assert beat_map.beats == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    assert beat_map.bpm == 120


def test_beats_stay_inside_the_track():
    assert FixedTempoBeats(92).beats(10.0).beats[-1] <= 10.0


def test_librosa_is_not_installed_here():
    with pytest.raises(BackendUnavailable, match="librosa"):
        LibrosaBeats().beats(10.0)


def test_unknown_beat_source_is_rejected():
    with pytest.raises(KeyError, match="unknown beat source"):
        get_beat_source("aubio")
