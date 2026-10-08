import io
from pathlib import Path

import pytest

from app.core import media
from app.services import uploads


def test_classify_recognises_photos_and_clips_regardless_of_case():
    assert uploads.classify("IMG_2231.JPG") == (uploads.PHOTO, ".jpg")
    assert uploads.classify("produk.webp") == (uploads.PHOTO, ".webp")
    assert uploads.classify("take 1.MP4") == (uploads.CLIP, ".mp4")
    assert uploads.classify("rekaman.mov") == (uploads.CLIP, ".mov")


def test_classify_rejects_other_files_and_lists_what_is_supported():
    with pytest.raises(uploads.UploadError) as error:
        uploads.classify("naskah.pdf")
    assert ".pdf" in str(error.value)
    assert ".jpg" in str(error.value)
    assert ".mp4" in str(error.value)


def test_classify_rejects_a_file_without_an_extension():
    with pytest.raises(uploads.UploadError):
        uploads.classify("photo")


def test_stored_names_never_reuse_the_uploaded_name():
    assert uploads.asset_id(0) == "a01"
    assert uploads.asset_path(9, ".png") == "assets/a10.png"
    assert uploads.display_name("C:/Users/rex/Desktop/foto produk.png") == "foto produk.png"
    assert uploads.display_name("..\\..\\evil.jpg") == "evil.jpg"
    assert uploads.display_name("") == "material"
    assert len(uploads.display_name("a" * 400)) == uploads.MAX_NAME_LENGTH


def test_music_file_keeps_only_a_known_audio_extension():
    assert uploads.music_file("track.MP3") == "music.mp3"
    assert uploads.music_file("C:/music/bed.wav") == "music.wav"
    with pytest.raises(uploads.UploadError):
        uploads.music_file("voice.mp4")
    with pytest.raises(uploads.UploadError):
        uploads.music_file("track.m4a.bak")


def test_byte_limits_differ_per_kind():
    assert uploads.byte_limit(uploads.CLIP) == uploads.MAX_CLIP_BYTES
    assert uploads.byte_limit(uploads.PHOTO) == uploads.MAX_PHOTO_BYTES
    assert uploads.MAX_CLIP_BYTES > uploads.MAX_PHOTO_BYTES


def test_save_upload_writes_the_stream_in_chunks(tmp_path):
    target = tmp_path / "assets" / "a01.jpg"
    size = uploads.save_upload(io.BytesIO(b"x" * 40), target, 1024)
    assert size == 40
    assert target.read_bytes() == b"x" * 40


def test_save_upload_refuses_a_file_over_the_limit_and_leaves_nothing_behind(tmp_path):
    target = tmp_path / "assets" / "a01.mp4"
    with pytest.raises(uploads.UploadError) as error:
        uploads.save_upload(io.BytesIO(b"x" * 4096), target, 1024)
    assert "larger than" in str(error.value)
    assert not target.exists()


def test_save_upload_refuses_an_empty_file(tmp_path):
    target = tmp_path / "assets" / "a01.jpg"
    with pytest.raises(uploads.UploadError):
        uploads.save_upload(io.BytesIO(b""), target, 1024)
    assert not target.exists()


def test_inspect_rejects_material_below_the_minimum_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr(
        media,
        "probe",
        lambda path: {"width": 320, "height": 240, "codec": "mjpeg", "duration": None},
    )
    with pytest.raises(uploads.UploadError) as error:
        uploads.inspect(uploads.PHOTO, tmp_path / "a01.jpg")
    assert "too small" in str(error.value)


def test_inspect_requires_a_readable_duration_for_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(
        media,
        "probe",
        lambda path: {"width": 1280, "height": 720, "codec": "h264", "duration": None},
    )
    with pytest.raises(uploads.UploadError):
        uploads.inspect(uploads.CLIP, tmp_path / "a01.mp4")


def test_inspect_reports_probe_failures_as_upload_errors(tmp_path, monkeypatch):
    def failing_probe(path):
        raise media.MediaError("ffprobe failed: the file has no video stream")

    monkeypatch.setattr(media, "probe", failing_probe)
    with pytest.raises(uploads.UploadError):
        uploads.inspect(uploads.CLIP, tmp_path / "a01.mp4")


def test_build_record_describes_the_material_for_the_ui():
    clip = uploads.build_record(
        1,
        uploads.CLIP,
        "D:/clips/take one.mp4",
        ".mp4",
        {"width": 1080, "height": 1920, "codec": "h264", "duration": 12.346},
        4096,
    )
    assert clip == {
        "id": "a02",
        "kind": "clip",
        "path": "assets/a02.mp4",
        "name": "take one.mp4",
        "hero": False,
        "size": 4096,
        "width": 1080,
        "height": 1920,
        "codec": "h264",
        "duration": 12.346,
        "scenes": [],
    }
    still = uploads.build_record(
        0,
        uploads.PHOTO,
        "foto.jpg",
        ".jpg",
        {"width": 1200, "height": 900, "codec": "mjpeg", "duration": None},
        10,
    )
    assert still["duration"] is None
    assert still["path"].endswith("a01.jpg")


def test_asset_paths_stay_inside_the_projects_asset_folder():
    record = uploads.build_record(
        3,
        uploads.PHOTO,
        "../../../etc/passwd.jpg",
        ".jpg",
        {"width": 800, "height": 800, "codec": "mjpeg", "duration": None},
        1,
    )
    stored = Path(record["path"])
    assert stored == Path("assets") / "a04.jpg"
    assert record["name"] == "passwd.jpg"
