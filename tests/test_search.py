"""Tests for search index builder and query API."""

from pathlib import Path

from mushi.core.search import SearchBuilder, SearchQuery, Searcher
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import SessionStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.filesystem import FilesystemStorage


def _setup(tmp_path: Path) -> FilesystemStorage:
    storage = FilesystemStorage(tmp_path)
    tw = TaskWorkflow(storage)
    pw = ProfileWorkflow(storage)
    tw.create_task(task_id="task-1", title="Design storage", tags=["storage", "phase2"])
    tw.create_task(task_id="task-2", title="Implement CLI", tags=["cli"])
    pw.save_profile(name="default", backend="opencode", settings={})

    sw = SessionWorkflow(storage)
    sw.start_session(
        session_id="session-1", task_id="task-1", profile_name="default",
        workspace_path="/repo", goal="Implement storage layer",
    )
    sw.finish_session(
        task_id="task-1", session_id="session-1",
        status=SessionStatus.SUCCEEDED, result_summary="Storage done",
    )
    return storage


def test_build_index_creates_search_files(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    builder = SearchBuilder(storage)
    builder.build_index()

    index_dir = storage.layout.search_index_dir
    assert index_dir.is_dir()
    files = list(index_dir.glob("*.json"))
    assert len(files) > 0


def test_build_index_records_are_rebuildable(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    builder = SearchBuilder(storage)

    builder.build_index()
    first_count = len(list(storage.layout.search_index_dir.glob("*.json")))
    builder.rebuild()
    second_count = len(list(storage.layout.search_index_dir.glob("*.json")))

    assert first_count == second_count


def test_search_returns_results_by_text(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    SearchBuilder(storage).build_index()

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(text="storage"))

    assert len(results) >= 1
    assert any("Design storage" in r.text for r in results)


def test_search_filters_by_record_type(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    SearchBuilder(storage).build_index()

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(record_type="task"))

    assert all(r.record_type == "task" for r in results)


def test_search_filters_by_backend(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    SearchBuilder(storage).build_index()

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(backend="opencode"))

    assert all(r.metadata.get("backend") == "opencode" for r in results)


def test_search_filters_by_tags(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    SearchBuilder(storage).build_index()

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(tags=["storage"]))

    assert len(results) >= 1


def test_search_returns_empty_for_no_match(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    SearchBuilder(storage).build_index()

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(text="zzz_nonexistent_zzz"))

    assert results == []


def test_search_returns_empty_when_no_index(tmp_path: Path) -> None:
    storage = _setup(tmp_path)

    searcher = Searcher(storage)
    results = searcher.search(SearchQuery(text="storage"))

    assert results == []


def test_search_after_rebuild_produces_same_results(tmp_path: Path) -> None:
    storage = _setup(tmp_path)
    builder = SearchBuilder(storage)
    builder.build_index()

    searcher = Searcher(storage)
    before = searcher.search(SearchQuery(text="storage"))

    builder.rebuild()
    after = searcher.search(SearchQuery(text="storage"))

    assert len(before) == len(after)
