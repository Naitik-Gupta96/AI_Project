import pytest

from ai_project.protocol import Judgment, PXPMessage, PXPTag, expected_tag

K = 3


@pytest.mark.parametrize(
    ("match", "agree", "changed", "j", "tag"),
    [
        # CatA: match and agree -> RATIFY, whatever else
        (True, True, False, 2, "RATIFY"),
        (True, True, True, 9, "RATIFY"),
        # CatB / CatC: exactly one -> REVISE if changed else REFUTE, at any j
        (True, False, True, 2, "REVISE"),
        (True, False, False, 2, "REFUTE"),
        (False, True, True, 9, "REVISE"),
        (False, True, False, 9, "REFUTE"),
        # CatD: neither -> REJECT only after k, else REVISE / REFUTE
        (False, False, False, K, "REFUTE"),
        (False, False, True, K, "REVISE"),
        (False, False, False, K + 1, "REJECT"),
        (False, False, True, K + 1, "REJECT"),
    ],
)
def test_algorithm_1_table(match, agree, changed, j, tag):
    assert expected_tag(j, Judgment(match, agree, changed), K) == PXPTag(tag)


def test_message_one_is_init_regardless_of_judgment():
    assert expected_tag(1, None, K) == PXPTag.INIT
    assert expected_tag(1, Judgment(False, False, False), K) == PXPTag.INIT


def test_reply_without_judgment_is_an_error():
    with pytest.raises(ValueError):
        expected_tag(2, None, K)


def test_tag_parsing_is_case_insensitive_and_strict():
    assert PXPTag.from_string(" ratify ") == PXPTag.RATIFY
    with pytest.raises(ValueError):
        PXPTag.from_string("AGREE")


def test_message_round_trip():
    m = PXPMessage("critic", "REFUTE", "B", "A breaks C3", 0.85,
                   judgment={"prediction_matches": False, "explanation_agrees": True,
                             "changed": False},
                   metadata={"k": [1]})
    again = PXPMessage.from_dict(m.to_dict())
    assert again.to_dict() == m.to_dict()
    assert again.tag == PXPTag.REFUTE
    assert again.judgment == Judgment(False, True, False)
    assert m.message_id.startswith("msg_")
