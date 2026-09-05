from __future__ import annotations

import pytest

from videobot.http import FetchError
from videobot.sources.footage import (
    Clip,
    LocalFootageSource,
    PexelsVideoSource,
    _best_rendition,
)

PEXELS_PAYLOAD = {
    "videos": [
        {
            "url": "https://www.pexels.com/video/water-1/",
            "duration": 12,
            "user": {"name": "A Photographer"},
            "video_files": [
                {"link": "https://x/4k.mp4", "width": 2160, "file_type": "video/mp4"},
                {"link": "https://x/hd.mp4", "width": 1080, "file_type": "video/mp4"},
                {"link": "https://x/small.mp4", "width": 640, "file_type": "video/mp4"},
            ],
        }
    ]
}


# --- local clips ----------------------------------------------------------


def _clip_files(directory, *names):
    for name in names:
        (directory / name).write_bytes(b"\x00")


def test_a_missing_folder_says_so(tmp_path):
    with pytest.raises(FetchError, match="not found"):
        LocalFootageSource(tmp_path / "nope").fetch("water", 3)


def test_a_folder_with_no_video_says_what_it_looked_for(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(FetchError, match=r"\.mp4"):
        LocalFootageSource(tmp_path).fetch("water", 3)


def test_local_clips_are_chosen_in_a_reproducible_order(tmp_path):
    """The cache depends on it; "whatever the filesystem returned" is not a choice."""
    _clip_files(tmp_path, "c.mp4", "a.mp4", "b.mov")
    picked = [c.src.rsplit("/", 1)[-1] for c in LocalFootageSource(tmp_path).fetch("water", 3)]

    assert picked == ["a.mp4", "b.mov", "c.mp4"]
    assert picked == [c.src.rsplit("/", 1)[-1] for c in LocalFootageSource(tmp_path).fetch("water", 3)]


def test_local_clips_are_found_in_subfolders(tmp_path):
    (tmp_path / "b-roll").mkdir()
    _clip_files(tmp_path / "b-roll", "deep.mp4")
    assert len(LocalFootageSource(tmp_path).fetch("water", 3)) == 1


def test_local_clips_are_marked_local_so_they_are_not_downloaded(tmp_path):
    _clip_files(tmp_path, "a.mp4")
    clip = LocalFootageSource(tmp_path).fetch("water", 1)[0]
    assert clip.local is True and clip.licence == "local"


# --- pexels ---------------------------------------------------------------


def test_a_missing_key_names_both_ways_out(monkeypatch):
    monkeypatch.delenv(PexelsVideoSource.KEY_ENV, raising=False)
    with pytest.raises(FetchError) as caught:
        PexelsVideoSource().fetch("water", 3)

    assert PexelsVideoSource.KEY_ENV in str(caught.value)
    assert "--footage" in str(caught.value)


def test_the_key_travels_in_a_header_never_in_the_url(monkeypatch):
    """A URL reaches logs, exception text and run.json. A key must not."""
    seen = {}

    def fake_get_json(url, params=None, headers=None):
        seen.update(url=url, params=params, headers=headers)
        return PEXELS_PAYLOAD

    monkeypatch.setattr("videobot.sources.footage.get_json", fake_get_json)
    PexelsVideoSource(key="secret-key").fetch("water", 3)

    assert seen["headers"] == {"Authorization": "secret-key"}
    assert "secret-key" not in seen["url"]
    assert "secret-key" not in str(seen["params"])


def test_pexels_results_carry_their_licence_and_credit(monkeypatch):
    monkeypatch.setattr(
        "videobot.sources.footage.get_json", lambda url, params=None, headers=None: PEXELS_PAYLOAD
    )
    clip = PexelsVideoSource(key="k").fetch("water", 3)[0]

    assert clip.credit == "A Photographer"
    assert "no attribution required" in clip.licence
    assert clip.duration_s == 12
    assert clip.local is False


def test_the_smallest_rendition_that_still_fills_the_frame_wins():
    """A 4K master costs minutes of download and is scaled back down anyway."""
    assert _best_rendition(PEXELS_PAYLOAD["videos"][0]["video_files"])["link"] == "https://x/hd.mp4"


def test_a_clip_that_cannot_fill_the_frame_is_not_offered():
    files = [{"link": "a", "width": 640, "file_type": "video/mp4"}]
    assert _best_rendition(files) is None


def test_non_mp4_renditions_are_ignored():
    files = [{"link": "a", "width": 1920, "file_type": "video/quicktime"}]
    assert _best_rendition(files) is None


# --- fitness for the frame ------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "aspect", "fits"),
    [
        (1080, 1920, "9:16", True),
        (1920, 1080, "9:16", False),   # a landscape clip crops to nothing
        (1920, 1080, "16:9", True),
        (1080, 1080, "1:1", True),
        (720, 1280, "9:16", False),    # below delivery width, upscaling shows
    ],
)
def test_clip_fitness_by_aspect(width, height, aspect, fits):
    clip = Clip(src="x", credit="", licence="", width=width, height=height, duration_s=10)
    assert clip.portrait_fit(aspect) is fits


def test_a_clip_shorter_than_a_scene_is_not_offered():
    clip = Clip(src="x", credit="", licence="", width=1080, height=1920, duration_s=1.0)
    assert clip.portrait_fit("9:16") is False
