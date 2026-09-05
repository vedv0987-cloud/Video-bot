from __future__ import annotations

import pytest

from videobot.audio.align import EstimatedAligner, WhisperXAligner, get_aligner
from videobot.audio.beats import FixedTempoBeats, LibrosaBeats, get_beat_source
from videobot.audio.speech import (
    BackendNotImplemented,
    BackendUnavailable,
    KokoroSpeech,
    NullSpeech,
    chunk_text,
    get_speech_backend,
    pcm16,
    wav_duration,
)

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


def test_kokoro_says_how_to_install_itself_when_missing():
    """A missing model must say how to get it, not raise ImportError."""
    try:
        import kokoro  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("kokoro is installed here, so there is no missing-install path to take")

    with pytest.raises(BackendUnavailable, match="Install it with"):
        KokoroSpeech().synthesize("hello")


@pytest.mark.parametrize(
    "call",
    [
        lambda: get_speech_backend("chatterbox").synthesize("hello"),
        lambda: WhisperXAligner().align(SECTIONS, 10.0),
        lambda: LibrosaBeats().beats(10.0),
    ],
    ids=["chatterbox", "whisperx", "librosa"],
)
def test_unwritten_backends_say_so_instead_of_blaming_the_install(call):
    """Telling someone to pip install code that was never written wastes a day."""
    with pytest.raises(BackendNotImplemented) as caught:
        call()

    assert "no implementation yet" in str(caught.value)
    assert "Install it with" not in str(caught.value)


# --- kokoro, without the model -------------------------------------------


def test_chunking_keeps_sentences_whole_and_under_the_ceiling():
    text = " ".join(f"Sentence number {n} says something about water." for n in range(20))
    chunks = chunk_text(text, limit=120)

    assert all(len(chunk) <= 120 for chunk in chunks)
    assert " ".join(chunks) == text


def test_chunking_is_a_pure_function_of_the_text():
    """The voice artifact is cached by digest — chunking must not drift."""
    text = "One. Two. Three."
    assert chunk_text(text) == chunk_text(text)


def test_an_overlong_sentence_breaks_at_a_clause_not_mid_word():
    text = "water matters a great deal, and thirst arrives late, so drink early in the day"
    chunks = chunk_text(text, limit=40)

    assert all(chunk in text for chunk in chunks)
    assert chunks[0].endswith("deal,")


def test_pcm16_clips_instead_of_wrapping_around():
    """A sample over full scale must saturate; wrapping is an audible click."""
    assert pcm16([2.0, -2.0]) == pcm16([1.0, -1.0])
    assert len(pcm16([0.0] * 5)) == 10


def test_pcm16_accepts_anything_array_like():
    class Tensor:
        def tolist(self):
            return [0.5]

    assert pcm16(Tensor()) == pcm16([0.5])


def test_kokoro_records_its_voice_and_seed_in_the_model_id():
    """Both change the audio, so both belong in the cache key."""
    assert KokoroSpeech(voice="af_bella", seed=7).model == "kokoro-82M:af_bella@7"
    assert KokoroSpeech().model != KokoroSpeech(seed=1).model


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


def test_unknown_beat_source_is_rejected():
    with pytest.raises(KeyError, match="unknown beat source"):
        get_beat_source("aubio")
