from ai_project.scheduler import PriorityArbiter
from tests.helpers import msg

TEAM = [("analyst", "analyst"), ("critic", "critic"), ("specialist", "specialist")]


def record(options_board, *messages):
    board = options_board(agents=[a for a, _ in TEAM])
    for m in messages:
        board.commit(m)
    return board.get_messages()


def test_first_turn_goes_to_registration_order(options_board):
    ranking = PriorityArbiter().rank(TEAM, record(options_board))
    assert [a.agent_id for a in ranking] == ["analyst", "critic", "specialist"]
    assert all(a.eligible for a in ranking)


def test_author_of_latest_message_is_not_eligible(options_board):
    ranking = PriorityArbiter().rank(TEAM, record(options_board, msg("analyst", "INIT", "A")))
    analyst = next(a for a in ranking if a.agent_id == "analyst")
    assert not analyst.eligible
    assert ranking[-1].agent_id == "analyst"


def test_critic_reviews_a_new_thesis_first(options_board):
    ranking = PriorityArbiter().rank(TEAM, record(options_board, msg("analyst", "INIT", "A")))
    assert ranking[0].agent_id == "critic"
    assert any("critic answers INIT" in r for r in ranking[0].reasons)


def test_specialist_answers_a_refute_first(options_board):
    messages = record(options_board, msg("analyst", "INIT", "A"),
                      msg("critic", "REFUTE", "B", judgment=(False, False, False)))
    ranking = PriorityArbiter().rank(TEAM, messages)
    assert ranking[0].agent_id == "specialist"


def test_pending_intervention_overrides_everything(options_board):
    messages = record(options_board, msg("analyst", "INIT", "A"),
                      msg("critic", "REFUTE", "B", judgment=(False, False, False)),
                      msg("specialist", "RATIFY", "B", judgment=(True, True, False)),
                      msg("analyst", "REJECT", "A", judgment=(False, False, False)))
    ranking = PriorityArbiter().rank(TEAM, messages, pending={"analyst"})
    assert ranking[0].agent_id == "analyst"
    assert ranking[0].eligible


def test_ranking_is_deterministic(options_board):
    messages = record(options_board, msg("analyst", "INIT", "A"))
    a = [x.to_dict() for x in PriorityArbiter().rank(TEAM, messages)]
    b = [x.to_dict() for x in PriorityArbiter().rank(TEAM, messages)]
    assert a == b
