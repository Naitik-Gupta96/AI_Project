from ai_project.protocol import GrammarContext, Position, PXPGrammar
from tests.helpers import msg

G = PXPGrammar(reject_after=3)
OPTS = ("A", "B", "C")


def ctx(j, peer=None, own=None, options=OPTS):
    def pos(p):
        return None if p is None else Position("x", p, "e")

    return GrammarContext(j=j, peer=pos(peer), own=pos(own), options=options)


def fields(errors):
    return {e.field for e in errors}


def test_first_message_must_be_init():
    assert G.check(msg("a", "INIT", "A"), ctx(1)) == []
    assert "tag" in fields(G.check(msg("a", "RATIFY", "A", judgment=(True, True, False)), ctx(1)))


def test_init_only_once():
    errors = G.check(msg("a", "INIT", "A"), ctx(2, peer="A"))
    assert "tag" in fields(errors)


def test_reply_needs_peer_and_judgment():
    assert "tag" in fields(G.check(msg("a", "REFUTE", "A", judgment=(False, False, False)),
                                   ctx(2, peer=None)))
    assert "judgment" in fields(G.check(msg("a", "REFUTE", "A"), ctx(2, peer="B")))


def test_prediction_must_be_an_option():
    errors = G.check(msg("a", "INIT", "Z"), ctx(1))
    assert "prediction" in fields(errors)


def test_free_form_predictions_are_not_option_checked():
    assert G.check(msg("a", "INIT", "about 42 kg"), ctx(1, options=())) == []


def test_prediction_matches_is_recomputed_for_options():
    # Peer B, no previous position: reference is the message itself (A) -> no match
    wrong = msg("a", "REFUTE", "A", judgment=(True, False, False))
    assert "judgment.prediction_matches" in fields(G.check(wrong, ctx(2, peer="B")))
    right = msg("a", "REFUTE", "A", judgment=(False, True, False))
    assert G.check(right, ctx(2, peer="B")) == []


def test_changed_must_be_false_on_first_reply():
    m = msg("a", "REVISE", "A", judgment=(False, True, True))
    assert "judgment.changed" in fields(G.check(m, ctx(2, peer="B")))


def test_moving_prediction_requires_changed():
    m = msg("a", "REFUTE", "C", judgment=(False, True, False))
    assert "judgment.changed" in fields(G.check(m, ctx(4, peer="B", own="A")))
    ok = msg("a", "REVISE", "C", judgment=(False, True, True))
    assert G.check(ok, ctx(4, peer="B", own="A")) == []


def test_tag_must_follow_algorithm_1():
    # neither matches nor agrees at j=4 > k=3 -> REJECT is required
    m = msg("a", "REFUTE", "A", judgment=(False, False, False))
    errors = G.check(m, ctx(4, peer="B", own="A"))
    assert any("requires REJECT" in e.message for e in errors)
    assert G.check(msg("a", "REJECT", "A", judgment=(False, False, False)),
                   ctx(4, peer="B", own="A")) == []


def test_reject_not_allowed_before_k():
    m = msg("a", "REJECT", "A", judgment=(False, False, False))
    errors = G.check(m, ctx(3, peer="B", own="A"))
    assert any("requires REFUTE" in e.message for e in errors)


def test_ratify_must_carry_peer_prediction():
    # previous position B matches peer B, but the message says A
    m = msg("a", "RATIFY", "A", judgment=(True, True, True))
    errors = G.check(m, ctx(4, peer="B", own="B"))
    assert any("aligns with the peer" in e.message for e in errors)
    assert G.check(msg("a", "RATIFY", "B", judgment=(True, True, False)),
                   ctx(4, peer="B", own="B")) == []


def test_structure_errors_short_circuit():
    errors = G.check(msg("", "INIT", " ", explanation="", confidence=1.5), ctx(1))
    assert fields(errors) == {"agent_id", "prediction", "explanation", "confidence"}
