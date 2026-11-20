import pytest

from ai_project.agents import Turn, TurnError, assemble
from ai_project.protocol import GrammarContext, Position, PXPGrammar, PXPTag

K = 3
OPTS = ("A", "B", "C")


def ctx(j, peer=None, own=None, options=OPTS):
    def pos(p):
        return None if p is None else Position("x", p, "e")

    return GrammarContext(j, pos(peer), pos(own), options)


def t(prediction, agrees=None, changed=None, matches=None):
    return Turn(prediction, "because", 0.7, agrees, matches, changed)


def test_first_message_is_init():
    m = assemble("a", t("A"), ctx(1), K)
    assert m.tag == PXPTag.INIT and m.judgment is None


def test_match_is_computed_for_options():
    m = assemble("a", t("B", agrees=True), ctx(2, peer="B"), K)
    assert m.judgment.prediction_matches and m.tag == PXPTag.RATIFY
    m = assemble("a", t("C", agrees=True), ctx(2, peer="B"), K)
    assert not m.judgment.prediction_matches and m.tag == PXPTag.REFUTE


def test_changed_is_false_on_first_reply_even_if_the_model_says_otherwise():
    m = assemble("a", t("C", agrees=True, changed=True), ctx(2, peer="B"), K)
    assert not m.judgment.changed and m.tag == PXPTag.REFUTE


def test_moving_the_prediction_counts_as_changed():
    m = assemble("a", t("C", agrees=True, changed=False), ctx(5, peer="B", own="A"), K)
    assert m.judgment.changed and m.tag == PXPTag.REVISE


def test_reasoning_change_counts_as_changed():
    m = assemble("a", t("A", agrees=True, changed=True), ctx(5, peer="B", own="A"), K)
    assert m.judgment.changed and m.tag == PXPTag.REVISE


def test_total_disagreement_after_k_is_reject():
    m = assemble("a", t("A", agrees=False, changed=False), ctx(K + 1, peer="B", own="A"), K)
    assert m.tag == PXPTag.REJECT
    m = assemble("a", t("A", agrees=False, changed=False), ctx(K, peer="B", own="A"), K)
    assert m.tag == PXPTag.REFUTE


def test_ratify_carries_the_peer_prediction():
    # previous position B matches the peer, explanation agrees, but the model now says C
    m = assemble("a", t("C", agrees=True), ctx(5, peer="B", own="B"), K)
    assert m.tag == PXPTag.RATIFY and m.prediction == "B"
    assert m.metadata["unsent_prediction"] == "C"


def test_free_form_needs_the_model_match_judgment():
    with pytest.raises(TurnError, match="prediction_matches"):
        assemble("a", t("about 4 kg", agrees=True), ctx(2, peer="4 kg", options=()), K)
    m = assemble("a", t("about 4 kg", agrees=True, matches=True),
                 ctx(2, peer="4 kg", options=()), K)
    assert m.tag == PXPTag.RATIFY and m.prediction == "about 4 kg"


def test_reply_needs_agreement_and_a_peer():
    with pytest.raises(TurnError, match="explanation_agrees"):
        assemble("a", t("A"), ctx(2, peer="B"), K)
    with pytest.raises(TurnError, match="no message from another agent"):
        assemble("a", t("A", agrees=True), ctx(2), K)


@pytest.mark.parametrize("j", [2, 3, 4, 6])
@pytest.mark.parametrize("own", [None, "A", "B"])
@pytest.mark.parametrize("prediction", OPTS)
@pytest.mark.parametrize("agrees", [True, False])
@pytest.mark.parametrize("changed", [True, False])
def test_assembled_messages_always_pass_the_grammar(j, own, prediction, agrees, changed):
    c = ctx(j, peer="B", own=own)
    message = assemble("a", t(prediction, agrees=agrees, changed=changed), c, K)
    assert PXPGrammar(K).check(message, c) == []
