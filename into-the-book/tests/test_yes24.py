import json

from src import yes24


def _cache(tmp_path, monkeypatch, day, pages):
    monkeypatch.setattr(yes24, "CACHE_DIR", tmp_path)
    for p, items in pages.items():
        path = tmp_path / yes24.NOVEL / f"{day}_p{p:02d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        status = 200 if items is not None else 404
        path.write_text(json.dumps({"status": status, "items": items or []}), encoding="utf-8")


def _items(n, prefix):
    return [{"sortOrder": i, "itemId": f"{prefix}{i}", "title": f"{prefix}{i}"} for i in range(1, n + 1)]


def test_rank_is_page_offset_plus_sort_order(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: _items(100, "a"), 2: _items(30, "b"), 3: []})
    df = yes24.fetch_day("2024-06-03")
    assert len(df) == 130
    assert df.loc[df["title"] == "b1", "rank"].item() == 101
    assert df["rank"].max() == 130


def test_max_rank_cut(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: _items(100, "a"), 2: _items(100, "b")})
    assert yes24.fetch_day("2024-06-03", max_rank=150)["rank"].max() == 150


def test_short_middle_page_does_not_stop(tmp_path, monkeypatch):
    """중간 페이지가 99개여도 다음 페이지를 계속 받는다 (버그 재발 방지).
    참고: 실제 API는 빈 번호를 남기지 않고 1~99로 다시 매긴다(2026-11-04 확인). 여기서는 멈추지 않는지만 본다."""
    short = [x for x in _items(100, "b") if x["sortOrder"] != 50]  # 99개
    _cache(tmp_path, monkeypatch, "2024-07-22",
           {1: _items(100, "a"), 2: short, 3: _items(100, "c"), 4: []})
    df = yes24.fetch_day("2024-07-22", max_rank=1000)
    assert len(df) == 299
    assert df.loc[df["title"] == "c1", "rank"].item() == 201


def test_no_data_day(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2023-01-02", {1: None})
    assert yes24.fetch_day("2023-01-02").empty


def test_find_rank_distinguishes_no_data_and_out_of_list(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: _items(100, "a"), 2: []})
    _cache(tmp_path, monkeypatch, "2023-01-02", {1: None})
    assert yes24.find_rank("2024-06-03", item_id="a7") == 7
    out = yes24.find_rank("2024-06-03", item_id="zzz")             # 200위 밖
    assert out == yes24.DEPTH + 1 and not (out <= 100)
    assert yes24.find_rank("2024-06-03", item_id="zzz", max_rank=1000) == 1001
    assert yes24.find_rank("2023-01-02", item_id="a7") is None    # 데이터 없는 날


def test_short_first_page_is_flagged(tmp_path, monkeypatch):
    short = [x for x in _items(100, "a") if x["sortOrder"] != 10]
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: short, 2: []})
    assert yes24.fetch_day("2024-06-03").attrs["short_pages"] == [1]


def test_empty_first_page_is_none(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: []})
    assert yes24.find_rank("2024-06-03", item_id="a1") is None


def test_default_depth_is_200_and_reads_only_two_pages(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, "2024-06-03", {1: _items(100, "a"), 2: _items(100, "b")})
    df = yes24.fetch_day("2024-06-03")          # 3페이지 캐시가 없어도 호출 안 함
    assert df["rank"].max() == 200


def test_api_blocked_without_permission_flag(monkeypatch):
    monkeypatch.delenv(yes24.ALLOW_ENV, raising=False)
    import pytest
    with pytest.raises(yes24.YES24Error):
        yes24._get({"categoryId": yes24.NOVEL})
