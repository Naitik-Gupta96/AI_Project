from ai_project.tasks import DecisionTask, Evidence, flash_talk_task, generate_tasks


def test_generation_is_seeded():
    assert generate_tasks(10, seed=1) == generate_tasks(10, seed=1)
    assert generate_tasks(10, seed=1) != generate_tasks(10, seed=2)


def test_task_round_trip():
    for task in generate_tasks(5, seed=0) + [flash_talk_task()]:
        assert DecisionTask.from_dict(task.to_dict()) == task


def test_ground_truth():
    task = flash_talk_task()
    assert task.feasible_options() == ("Option B",)
    assert task.best_feasible() == "Option B"
    infeasible = DecisionTask("t", "q", ("X",), {"critic": Evidence(objections={"X": "no"})})
    assert infeasible.best_feasible() is None


def test_board_metadata_is_public_only():
    assert set(flash_talk_task().board_metadata()) == {"task_id", "options"}
