import json
import subprocess
from pathlib import Path

import pytest

from app.core import media

PROBE_JSON = json.dumps(
    {
        "streams": [
            {"codec_type": "audio", "codec_name": "aac"},
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "duration": "12.3456",
            },
        ],
        "format": {"duration": "12.3456"},
    }
)


def test_parse_probe_reads_the_video_stream_and_rounds_the_duration():
    assert media.parse_probe(PROBE_JSON) == {
        "width": 1920,
        "height": 1080,
        "codec": "h264",
        "duration": 12.346,
    }


def test_parse_probe_accepts_a_still_image_without_duration():
    raw = json.dumps(
        {"streams": [{"codec_type": "video", "codec_name": "mjpeg", "width": 1200, "height": 900}]}
    )
    info = media.parse_probe(raw)
    assert (info["width"], info["height"], info["duration"]) == (1200, 900, None)


def test_parse_probe_rejects_a_file_without_a_video_stream():
    with pytest.raises(media.MediaError):
        media.parse_probe(json.dumps({"streams": [{"codec_type": "audio"}]}))


def test_parse_scene_times_dedupes_sorts_and_drops_the_opening_frame():
    text = (
        "frame:0    pts:0       pts_time:0\n"
        "lavfi.scd.time=0\n"
        "frame:60   pts:30720   pts_time:2\n"
        "lavfi.scd.mafd=29.434\n"
        "lavfi.scd.score=28.663\n"
        "lavfi.scd.time=2\n"
        "lavfi.scd.time=7.5\n"
        "lavfi.scd.time=2.000\n"
    )
    assert media.parse_scene_times(text) == [2.0, 7.5]


def test_parse_scene_times_ignores_scores_and_returns_nothing_without_cuts():
    assert media.parse_scene_times("lavfi.scd.score=28.663\nframe:1 pts:512 pts_time:0.033\n") == []


def _capture_argv(monkeypatch, result=0, create=False) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if create:
            target = Path(argv[-1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"frame")
        return subprocess.CompletedProcess(argv, result, stdout="", stderr="")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    return calls


def test_make_thumbnail_does_not_seek_for_a_still(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch, create=True)
    media.make_thumbnail(tmp_path / "foto.jpg", tmp_path / "thumb.jpg", 0.0, 480)
    assert "-ss" not in calls[0]


def test_make_thumbnail_seeks_for_a_clip_frame(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch, create=True)
    media.make_thumbnail(tmp_path / "klip.mp4", tmp_path / "thumb.jpg", 4.5, 480)
    argv = calls[0]
    assert argv[argv.index("-ss") + 1] == "4.500"


def test_make_thumbnail_reports_a_missing_frame(monkeypatch, tmp_path):
    _capture_argv(monkeypatch, create=False)
    with pytest.raises(media.MediaError):
        media.make_thumbnail(tmp_path / "foto.jpg", tmp_path / "thumb.jpg", 0.0, 480)


def test_freeze_segment_seeks_only_when_there_is_footage_to_skip(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch, create=True)
    media.freeze_segment(tmp_path / "klip.mp4", tmp_path / "hold.mp4", 0.0, 4.2)
    assert "-ss" not in calls[0]
    assert "-t" in calls[0]
    calls.clear()
    media.freeze_segment(tmp_path / "klip.mp4", tmp_path / "hold.mp4", 2.0, 4.2)
    assert calls[0][calls[0].index("-ss") + 1] == "2.000"
