import pytest

from app.services import shotlist


def _photo(asset_id="a01", hero=False):
    return {
        "id": asset_id,
        "kind": "photo",
        "path": f"assets/{asset_id}.jpg",
        "name": f"{asset_id}.jpg",
        "duration": None,
        "scenes": [],
        "hero": hero,
    }


def _clip(asset_id="a02", duration=10.0, scenes=None, hero=False):
    return {
        "id": asset_id,
        "kind": "clip",
        "path": f"assets/{asset_id}.mp4",
        "name": f"{asset_id}.mp4",
        "duration": duration,
        "scenes": scenes if scenes is not None else [{"start": 0.0, "end": duration}],
        "hero": hero,
    }


def _lines(count=3, slot=2.5):
    return [
        {
            "id": f"L{index}",
            "section": "solution",
            "text": f"line {index}",
            "hint": "",
            "overlay": None,
            "start": round((index - 1) * slot, 3),
            "end": round(index * slot, 3),
        }
        for index in range(1, count + 1)
    ]


def test_scene_segments_cover_the_clip_and_merge_slivers():
    assert shotlist.scene_segments([2.0, 2.2, 5.0, 9.9], 10.0) == [
        {"start": 0.0, "end": 2.0},
        {"start": 2.0, "end": 5.0},
        {"start": 5.0, "end": 10.0},
    ]


def test_scene_segments_treat_a_clip_that_never_cuts_as_one_scene():
    assert shotlist.scene_segments([], 4.0) == [{"start": 0.0, "end": 4.0}]


def test_scene_segments_is_empty_without_a_length():
    assert shotlist.scene_segments([1.0], 0.0) == []


def test_shot_windows_offer_several_starts_inside_a_long_scene():
    assert shotlist.shot_windows(_clip(duration=20.0), 4.0) == [(0, 0.0), (0, 4.0), (0, 8.0)]


def test_shot_windows_prefer_a_scene_that_fits_over_a_cut_crossing_window():
    clip = _clip(
        duration=10.0,
        scenes=[
            {"start": 0.0, "end": 1.0},
            {"start": 1.0, "end": 6.0},
            {"start": 6.0, "end": 10.0},
        ],
    )
    windows = shotlist.shot_windows(clip, 3.0)
    assert windows[0] == (0, 1.0)
    assert (1, 0.0) in windows


def test_shot_windows_treat_a_clip_without_scenes_as_one_scene():
    assert shotlist.shot_windows(_clip(duration=6.0, scenes=[]), 2.0)[0] == (0, 0.0)


def test_shot_windows_ask_for_a_freeze_when_the_clip_is_too_short():
    assert shotlist.shot_windows(_clip(duration=1.5), 3.0) == [(shotlist.FREEZE_RANK, 0.0)]


def test_pick_window_moves_to_fresh_footage_after_each_pass():
    clip = _clip(duration=20.0)
    assert shotlist.pick_window(clip, 4.0, {}) == (shotlist.MODE_TRIM, 0.0)
    assert shotlist.pick_window(clip, 4.0, {"a02": [(0.0, 4.0)]}) == (shotlist.MODE_TRIM, 4.0)
    assert shotlist.pick_window(clip, 4.0, {"a02": [(0.0, 4.0), (4.0, 8.0)]}) == (
        shotlist.MODE_TRIM,
        8.0,
    )


def test_pick_window_freezes_only_when_the_whole_clip_is_shorter_than_the_slot():
    assert shotlist.pick_window(_clip("a03", duration=1.0), 2.5, {}) == (
        shotlist.MODE_FREEZE,
        0.0,
    )


def test_build_shotlist_leads_with_the_hero_and_follows_the_user_order():
    assets = [_photo("a01"), _clip("a02", duration=8.0), _photo("a03", hero=True)]
    result = shotlist.build_shotlist(_lines(3, slot=2.5), assets)
    shots = result["shots"]
    assert [shot["asset"] for shot in shots] == ["a03", "a01", "a02"]
    assert [shot["id"] for shot in shots] == ["S1", "S2", "S3"]
    assert [shot["line"] for shot in shots] == ["L1", "L2", "L3"]
    assert shots[0]["mode"] == shotlist.MODE_PHOTO
    assert shots[0]["source_start"] is None
    assert (shots[0]["start"], shots[0]["end"]) == (0.0, 2.5)
    assert (shots[1]["start"], shots[1]["end"]) == (2.5, 5.0)
    assert shots[2]["mode"] == shotlist.MODE_TRIM
    assert shots[2]["source_start"] == 0.0
    assert all(shot["locked"] is False for shot in shots)
    assert all(shot["overlay"] is None for shot in shots)


def test_build_shotlist_never_repeats_a_neighbouring_asset_while_alternatives_exist():
    assets = [_photo("a01"), _photo("a02")]
    shots = shotlist.build_shotlist(_lines(5, slot=2.0), assets)["shots"]
    assert [shot["asset"] for shot in shots] == ["a01", "a02", "a01", "a02", "a01"]


def test_build_shotlist_reuses_the_only_asset_for_every_line():
    shots = shotlist.build_shotlist(_lines(3, slot=2.0), [_photo("a01")])["shots"]
    assert [shot["asset"] for shot in shots] == ["a01", "a01", "a01"]


def test_build_shotlist_shows_different_footage_when_a_clip_comes_back():
    clip = _clip("a02", duration=30.0)
    shots = shotlist.build_shotlist(_lines(2, slot=3.0), [clip])["shots"]
    assert [shot["source_start"] for shot in shots] == [0.0, 3.0]


def test_build_shotlist_keeps_locked_lines_on_their_asset_and_window():
    assets = [_photo("a01"), _clip("a02", duration=8.0)]
    previous = {
        "shots": [
            {
                "line": "L1",
                "asset": "a02",
                "mode": shotlist.MODE_TRIM,
                "source_start": 2.0,
                "overlay": "2s / hari",
                "locked": True,
            },
            {"line": "L2", "asset": "a01", "mode": shotlist.MODE_PHOTO, "locked": False},
        ]
    }
    shots = shotlist.build_shotlist(_lines(2, slot=2.5), assets, previous)["shots"]
    assert shots[0]["asset"] == "a02"
    assert shots[0]["source_start"] == 2.0
    assert shots[0]["overlay"] == "2s / hari"
    assert shots[0]["locked"] is True
    assert shots[1]["asset"] == "a01"
    assert shots[1]["locked"] is False


def test_build_shotlist_keeps_typed_overlays_when_nothing_is_locked():
    assets = [_photo("a01"), _clip("a02", duration=8.0)]
    previous = {
        "shots": [
            {
                "line": "L1",
                "asset": "a02",
                "mode": "trim",
                "source_start": 2.0,
                "overlay": "KODE 10%",
            },
            {"line": "L2", "asset": "a01", "mode": "photo", "overlay": None, "locked": False},
        ]
    }
    shots = shotlist.build_shotlist(_lines(2, slot=2.5), assets, previous)["shots"]
    assert shots[0]["overlay"] == "KODE 10%"
    assert shots[1]["overlay"] is None
    assert shots[0]["asset"] == "a01"


def test_build_shotlist_uses_the_assignment_the_model_proposed():
    assets = [_photo("a01"), _photo("a02"), _clip("a03", duration=9.0)]
    result = shotlist.build_shotlist(
        _lines(3, slot=2.5),
        assets,
        assignment={"L1": "a03", "L2": "a01", "L3": "a02"},
        matched_by="model",
        notes="clip leads",
    )
    assert [shot["asset"] for shot in result["shots"]] == ["a03", "a01", "a02"]
    assert result["matched_by"] == "model"
    assert result["notes"] == "clip leads"


def test_build_shotlist_ignores_unknown_ids_and_fills_the_rest_by_rotation():
    assets = [_photo("a01"), _photo("a02"), _photo("a03")]
    result = shotlist.build_shotlist(
        _lines(3, slot=2.0),
        assets,
        assignment={"L1": "a99", "L2": "a02"},
        matched_by="model",
    )
    shots = result["shots"]
    assert shots[1]["asset"] == "a02"
    assert {shot["asset"] for shot in shots} == {"a01", "a02", "a03"}
    assert shots[0]["asset"] != shots[1]["asset"]


def test_build_shotlist_lets_a_lock_win_over_the_assignment():
    assets = [_photo("a01"), _photo("a02")]
    previous = {
        "shots": [{"line": "L1", "asset": "a01", "mode": "photo", "overlay": None, "locked": True}]
    }
    result = shotlist.build_shotlist(
        _lines(2, slot=2.0), assets, previous, assignment={"L1": "a02", "L2": "a01"}
    )
    assert result["shots"][0]["asset"] == "a01"


def test_build_shotlist_lets_the_hero_open_the_video_even_with_an_assignment():
    assets = [_photo("a01"), _clip("a02", duration=8.0, hero=True), _photo("a03")]
    result = shotlist.build_shotlist(
        _lines(3, slot=2.0),
        assets,
        assignment={"L1": "a03", "L2": "a01", "L3": "a02"},
        matched_by="model",
    )
    shots = result["shots"]
    assert shots[0]["asset"] == "a02"
    assert shots[1]["asset"] == "a01"
    assert shots[2]["asset"] == "a02"


def test_build_shotlist_reports_the_rotation_when_there_is_no_assignment():
    result = shotlist.build_shotlist(_lines(1, slot=2.0), [_photo("a01")])
    assert result["matched_by"] == "rotation"
    assert result["notes"] == ""


def test_build_shotlist_without_material_returns_no_shots():
    assert shotlist.build_shotlist(_lines(2), [])["shots"] == []
    assert shotlist.build_shotlist([], [_photo("a01")])["shots"] == []


def test_apply_edits_marks_the_result_as_edited():
    assets = [_photo("a01"), _photo("a02")]
    lines = _lines(2, slot=2.0)
    base = shotlist.build_shotlist(lines, assets)
    edited = shotlist.apply_edits(base, lines, assets, [{"line": "L1", "asset": "a02"}])
    assert edited["matched_by"] == "manual"


def test_apply_edits_swaps_one_asset_and_keeps_the_other_shots_in_place():
    assets = [_photo("a01"), _clip("a02", duration=8.0), _clip("a03", duration=8.0)]
    lines = _lines(3, slot=2.5)
    base = shotlist.build_shotlist(lines, assets)
    assert [shot["asset"] for shot in base["shots"]] == ["a01", "a02", "a03"]
    edited = shotlist.apply_edits(
        base,
        lines,
        assets,
        [{"line": "L2", "asset": "a03", "overlay": "Rp 299.000", "locked": True}],
    )
    shots = edited["shots"]
    assert [shot["asset"] for shot in shots] == ["a01", "a03", "a03"]
    assert shots[0]["asset"] == "a01"
    assert shots[1]["overlay"] == "Rp 299.000"
    assert shots[1]["locked"] is True
    assert shots[1]["source_start"] != shots[2]["source_start"]
    assert [shot["start"] for shot in shots] == [0.0, 2.5, 5.0]


def test_apply_edits_leaves_the_picture_alone_when_only_the_overlay_changes():
    assets = [_photo("a01", hero=True), _clip("a02", duration=8.0)]
    lines = _lines(2, slot=2.0)
    base = shotlist.build_shotlist(lines, assets)
    edited = shotlist.apply_edits(base, lines, assets, [{"line": "L2", "overlay": "Diskon 50%"}])
    before, after = base["shots"][1], edited["shots"][1]
    assert after["asset"] == before["asset"]
    assert after["mode"] == before["mode"]
    assert after["source_start"] == before["source_start"]
    assert (after["start"], after["end"]) == (before["start"], before["end"])
    assert after["overlay"] == "Diskon 50%"
    assert after["locked"] is False


def test_apply_edits_can_unlock_a_line():
    assets = [_photo("a01")]
    lines = _lines(1, slot=2.0)
    base = shotlist.build_shotlist(lines, assets)
    base["shots"][0]["locked"] = True
    edited = shotlist.apply_edits(base, lines, assets, [{"line": "L1", "locked": False}])
    assert edited["shots"][0]["locked"] is False


def test_apply_edits_asks_for_a_freeze_when_the_new_asset_is_too_short():
    assets = [_photo("a01"), _clip("a02", duration=1.0)]
    lines = _lines(1, slot=3.0)
    base = shotlist.build_shotlist(lines, assets)
    edited = shotlist.apply_edits(base, lines, assets, [{"line": "L1", "asset": "a02"}])
    assert edited["shots"][0]["mode"] == shotlist.MODE_FREEZE


def test_apply_edits_rejects_unknown_targets():
    assets = [_photo("a01")]
    lines = _lines(1, slot=2.0)
    base = shotlist.build_shotlist(lines, assets)
    with pytest.raises(ValueError):
        shotlist.apply_edits(base, lines, assets, [{"line": "L9", "asset": "a01"}])
    with pytest.raises(ValueError):
        shotlist.apply_edits(base, lines, assets, [{"line": "L1", "asset": "a99"}])
