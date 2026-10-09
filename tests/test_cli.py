from todo_qt.cli import main


def test_main_returns_success_exit_code() -> None:
    assert main() == 0
