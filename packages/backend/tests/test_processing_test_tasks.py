from cadmus.processing import execute_test_task


def test_test_task_returns_deterministic_result() -> None:
    assert execute_test_task("hello") == {"echo": "hello"}
