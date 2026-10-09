"""Drag to reorder: final_index, the model's drop handling, controller and window."""

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView
from pytestqt.qtbot import QtBot

from todo_qt.domain import TaskId
from todo_qt.services import PlanService, StoreWriteError
from todo_qt.ui.controller import UiController
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.messages import save_failure_message
from todo_qt.ui.task_model import TaskListModel, final_index

from .fakes import FakeStore, MakeService, RecordingStore, T, make_plan, make_slot, make_task

_ROOT = QModelIndex()


def _abc() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(9), T(10))),
            make_task("b", "B", make_slot(T(10), T(11, 30))),
            make_task("c", "C", make_slot(T(14), T(14, 30))),
        )
    )


def _rows(service: PlanService) -> list[tuple[str, object, object]]:
    return [(t.title, t.slot.start, t.slot.end) for t in service.plan.tasks]


def _wired(service: PlanService) -> tuple[TaskListModel, list[str]]:
    messages: list[str] = []
    model: TaskListModel
    controller = UiController(service, messages.append, lambda: model.refresh())
    model = TaskListModel(service, move=controller.move_task)
    return model, messages


def _drop(model: TaskListModel, row: int, drop_row: int) -> bool:
    data = model.mimeData([model.index(row)])
    return model.dropMimeData(data, Qt.DropAction.MoveAction, drop_row, 0, _ROOT)


@pytest.mark.parametrize(
    ("old", "drop_row", "size", "expected"),
    [
        (2, 1, 3, 1),  # up
        (0, 3, 3, 2),  # down, to the end
        (0, 2, 3, 1),  # down, in the middle
        (1, 1, 3, 1),  # same position (before itself)
        (1, 2, 3, 1),  # same position (after itself)
        (0, -1, 3, 2),  # append
        (2, 0, 3, 0),  # top
    ],
)
def test_final_index_converts_the_drop_insertion_point(
    old: int, drop_row: int, size: int, expected: int
) -> None:
    assert final_index(old, drop_row, size) == expected


def test_ui_drag_task_between_a_and_b_rechains_times(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)

    accepted = _drop(model, 2, 1)

    assert (accepted, _rows(service), model.rowCount()) == (
        True,
        [("A", T(9), T(10)), ("C", T(10), T(10, 30)), ("B", T(10, 30), T(12))],
        3,
    )


def test_ui_drag_to_the_end_appends(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)

    accepted = _drop(model, 0, -1)

    assert (accepted, [t.title for t in service.plan.tasks]) == (True, ["B", "C", "A"])


def test_ui_drag_first_task_down_snaps_to_day_start(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)

    _drop(model, 0, 2)

    assert _rows(service) == [
        ("B", T(9), T(10, 30)),
        ("A", T(10, 30), T(11, 30)),
        ("C", T(11, 30), T(12)),
    ]


def test_ui_drop_at_own_position_changes_nothing_and_does_not_save(
    make_service: MakeService, recording_store: RecordingStore
) -> None:
    recording_store.inner = _abc()
    service = make_service(recording_store)
    model, _ = _wired(service)
    before = service.plan

    accepted = _drop(model, 1, 2)

    assert (accepted, service.plan, recording_store.saves) == (True, before, [])


def test_ui_drop_with_wrong_action_is_rejected(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)
    before = service.plan
    data = model.mimeData([model.index(2)])

    accepted = model.dropMimeData(data, Qt.DropAction.CopyAction, 1, 0, _ROOT)

    assert (accepted, service.plan) == (False, before)


def test_ui_drop_with_foreign_mime_data_is_rejected(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)
    before = service.plan
    foreign = QMimeData()
    foreign.setText("t1")

    accepted = model.dropMimeData(foreign, Qt.DropAction.MoveAction, 1, 0, _ROOT)

    assert (accepted, service.plan) == (False, before)


def test_ui_drop_with_unknown_task_id_is_rejected(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)
    before = service.plan
    data = model.mimeData([model.index(2)])
    data.setData(model.mimeTypes()[0], b"nope")

    accepted = model.dropMimeData(data, Qt.DropAction.MoveAction, 1, 0, _ROOT)

    assert (accepted, service.plan) == (False, before)


def test_ui_drop_with_undecodable_payload_is_rejected(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)
    before = service.plan
    data = model.mimeData([model.index(2)])
    data.setData(model.mimeTypes()[0], b"\xff\xfe")

    accepted = model.dropMimeData(data, Qt.DropAction.MoveAction, 1, 0, _ROOT)

    assert (accepted, service.plan) == (False, before)


def test_ui_drop_onto_an_item_is_rejected(make_service: MakeService) -> None:
    service = make_service(_abc())
    model, _ = _wired(service)
    data = model.mimeData([model.index(2)])

    accepted = model.dropMimeData(data, Qt.DropAction.MoveAction, -1, 0, model.index(0))

    assert (accepted, [t.title for t in service.plan.tasks]) == (False, ["A", "B", "C"])


def test_ui_model_flags_allow_drag_on_items_and_drop_on_root_only(
    make_service: MakeService,
) -> None:
    model, _ = _wired(make_service(_abc()))

    item = model.flags(model.index(0))
    root = model.flags(_ROOT)

    assert (
        bool(item & Qt.ItemFlag.ItemIsDragEnabled),
        bool(item & Qt.ItemFlag.ItemIsDropEnabled),
        bool(root & Qt.ItemFlag.ItemIsDropEnabled),
        model.supportedDropActions(),
    ) == (True, False, True, Qt.DropAction.MoveAction)


def test_ui_model_does_not_remove_rows_itself(make_service: MakeService) -> None:
    model, _ = _wired(make_service(_abc()))

    assert (model.removeRows(0, 1), model.rowCount()) == (False, 3)


def test_ui_controller_move_task_notifies_save_failure(make_service: MakeService) -> None:
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store = _abc()
    store.save_error = error
    service = make_service(store)
    messages: list[str] = []
    changes: list[int] = []
    controller = UiController(service, messages.append, lambda: changes.append(1))

    accepted = controller.move_task(TaskId("c"), 1)

    assert (accepted, messages, changes) == (True, [save_failure_message(error)], [1])


@pytest.mark.parametrize(("task_id", "index"), [("c", 7), ("c", -1), ("zzz", 0)])
def test_ui_controller_move_task_rejects_bad_index_or_id(
    make_service: MakeService, task_id: str, index: int
) -> None:
    service = make_service(_abc())
    messages: list[str] = []
    changes: list[int] = []
    controller = UiController(service, messages.append, lambda: changes.append(1))

    accepted = controller.move_task(TaskId(task_id), index)

    assert (accepted, len(messages), changes) == (False, 1, [])


def test_ui_window_list_view_uses_internal_move(qtbot: QtBot, make_service: MakeService) -> None:
    window = MainWindow(make_service(_abc()))
    qtbot.addWidget(window)

    view = window.list_view

    assert (
        view.dragDropMode(),
        view.defaultDropAction(),
        view.dragEnabled(),
    ) == (QAbstractItemView.DragDropMode.InternalMove, Qt.DropAction.MoveAction, True)


# Known gap: no test drives a real QListView drag. InternalMove requires
# event.source() == view, which cannot be set up under the offscreen platform, so
# the drop is driven through the model's mimeData/dropMimeData instead.
def _window_rows(window: MainWindow) -> list[str]:
    return [str(window.model.index(i).data()).replace("\n", " | ") for i in range(3)]


def _spy_resets(window: MainWindow) -> list[int]:
    resets: list[int] = []
    window.model.modelReset.connect(lambda: resets.append(1))
    return resets


def test_ui_window_drop_moves_task_and_refreshes_view_once(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = MainWindow(make_service(_abc()))
    qtbot.addWidget(window)
    resets = _spy_resets(window)

    accepted = _drop(window.model, 2, 1)

    assert (accepted, len(resets), _window_rows(window)) == (
        True,
        1,
        [
            "A | 2026-01-02 09:00 - 2026-01-02 10:00",
            "C | 2026-01-02 10:00 - 2026-01-02 10:30",
            "B | 2026-01-02 10:30 - 2026-01-02 12:00",
        ],
    )


def test_ui_window_drop_at_own_position_does_not_refresh(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = MainWindow(make_service(_abc()))
    qtbot.addWidget(window)
    resets = _spy_resets(window)

    accepted = _drop(window.model, 1, 2)

    assert (accepted, len(resets)) == (True, 0)


def test_ui_window_rejected_drop_does_not_refresh(qtbot: QtBot, make_service: MakeService) -> None:
    window = MainWindow(make_service(_abc()))
    qtbot.addWidget(window)
    resets = _spy_resets(window)
    data = window.model.mimeData([window.model.index(2)])

    accepted = window.model.dropMimeData(data, Qt.DropAction.CopyAction, 1, 0, _ROOT)

    assert (accepted, len(resets)) == (False, 0)
