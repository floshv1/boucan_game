import pytest

from game import packs_store


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PACKS_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))


def test_save_assigns_id_and_timestamps_and_roundtrips():
    saved = packs_store.save_pack(
        {
            "name": "Soirée",
            "mode": "qcm",
            "tags": ["musique"],
            "items": [{"question": "Q", "choices": ["a", "b", "c", "d"], "correct": 1, "points": 1000}],
        }
    )
    assert saved["id"] and saved["created_at"] and saved["updated_at"]
    got = packs_store.get_pack(saved["id"])
    assert got["name"] == "Soirée"
    assert got["items"][0]["correct"] == 1
    assert got["items"][0]["image"] is None


def test_list_returns_summaries_sorted():
    a = packs_store.save_pack({"name": "A", "mode": "buzzer", "items": [{"question": "x", "answer": "y", "points": 1}]})
    b = packs_store.save_pack({"name": "B", "mode": "qcm", "items": []})
    summaries = packs_store.list_packs()
    user = [s for s in summaries if not s["builtin"]]
    assert {s["id"] for s in user} == {a["id"], b["id"]}
    assert all("correct" not in s for s in summaries)  # summary only
    assert all(set(s.keys()) == {"id", "name", "mode", "count", "tags", "updated_at", "builtin"} for s in summaries)


def test_list_includes_builtin_starter_packs():
    summaries = packs_store.list_packs()
    builtins = [s for s in summaries if s["builtin"]]
    assert builtins, "expected built-in starter packs in the list"
    assert {"builtin-qcm-culture", "builtin-buzzer-culture"} <= {s["id"] for s in builtins}


def test_get_builtin_pack_returns_full_items():
    pack = packs_store.get_pack("builtin-qcm-culture")
    assert pack is not None
    assert pack["mode"] == "qcm"
    assert len(pack["items"]) >= 5
    assert pack["items"][0]["question"]


def test_cannot_overwrite_builtin_pack():
    saved = packs_store.save_pack({"id": "builtin-qcm-culture", "name": "Hack", "mode": "qcm", "items": []})
    assert saved["id"] != "builtin-qcm-culture"  # saved as a fresh user pack instead
    # the built-in is still served unchanged
    assert packs_store.get_pack("builtin-qcm-culture")["name"] == "Culture générale (QCM)"


def test_validate_rejects_bad_mode():
    with pytest.raises(ValueError):
        packs_store.validate_pack({"name": "x", "mode": "texte", "items": []})


def test_validate_rejects_empty_name():
    with pytest.raises(ValueError):
        packs_store.validate_pack({"name": "", "mode": "qcm", "items": []})


def test_qcm_item_normalized_to_four_choices():
    saved = packs_store.save_pack(
        {"name": "x", "mode": "qcm", "items": [{"question": "q", "choices": ["a"], "correct": 9}]}
    )
    item = packs_store.get_pack(saved["id"])["items"][0]
    assert len(item["choices"]) == 4
    assert item["correct"] == 0


def test_blindtest_item_normalized():
    saved = packs_store.save_pack(
        {"name": "x", "mode": "blindtest", "items": [{"spotify_track_id": "abc", "title": "T", "artist": "A"}]}
    )
    item = packs_store.get_pack(saved["id"])["items"][0]
    assert item["uri"] == "spotify:track:abc"
    assert item["points_title"] == 1
    # origin defaults present even when omitted
    assert item["origin"] == ""
    assert item["origin_type"] == ""
    assert item["points_origin"] == 1


def test_blindtest_item_preserves_origin():
    saved = packs_store.save_pack(
        {
            "name": "x",
            "mode": "blindtest",
            "items": [
                {
                    "spotify_track_id": "abc",
                    "title": "Main Theme",
                    "artist": "Koji Kondo",
                    "origin": "The Legend of Zelda",
                    "origin_type": "jeu_video",
                    "points_origin": 3,
                }
            ],
        }
    )
    item = packs_store.get_pack(saved["id"])["items"][0]
    assert item["origin"] == "The Legend of Zelda"
    assert item["origin_type"] == "jeu_video"
    assert item["points_origin"] == 3


def test_delete_removes_pack():
    saved = packs_store.save_pack({"name": "x", "mode": "qcm", "items": []})
    assert packs_store.delete_pack(saved["id"]) is True
    assert packs_store.get_pack(saved["id"]) is None
    assert packs_store.delete_pack("nope") is False


def test_update_preserves_id_and_created_at():
    saved = packs_store.save_pack({"name": "x", "mode": "qcm", "items": []})
    saved["name"] = "renamed"
    again = packs_store.save_pack(saved)
    assert again["id"] == saved["id"]
    assert again["created_at"] == saved["created_at"]
    assert packs_store.get_pack(saved["id"])["name"] == "renamed"
