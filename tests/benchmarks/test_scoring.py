import random

import pytest

from ai_project.benchmarks.scoring import (
    lcs_length,
    list_f1,
    numbers_match,
    parse_number,
    rouge_1,
    rouge_l,
    tokenize,
)


def lcs_dp(a, b):
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            best = max(table[i][j + 1], table[i + 1][j])
            table[i + 1][j + 1] = table[i][j] + 1 if x == y else best
    return table[-1][-1]


def test_bit_parallel_lcs_matches_dynamic_programming():
    rng = random.Random(0)
    for _ in range(300):
        a = [rng.choice("abcde") for _ in range(rng.randint(0, 40))]
        b = [rng.choice("abcde") for _ in range(rng.randint(0, 40))]
        assert lcs_length(a, b) == lcs_dp(a, b)


def test_tokenize_splits_cjk_and_latin():
    tokens = tokenize("电池包 uses 3.5 kWh", use_jieba=False)
    assert tokens == ["电", "池", "包", "uses", "3.5", "kwh"]


def test_rouge_l():
    assert rouge_l("the cat sat on the mat", "the cat sat on the mat")["f1"] == 1.0
    assert rouge_l("", "anything")["f1"] == 0.0
    score = rouge_l("轻量化电池包设计", "电池包的轻量化与结构设计", use_jieba=False)
    assert 0 < score["f1"] < 1
    assert score["recall"] == pytest.approx(5 / 12)  # LCS "电池包" + "设计" (or "轻量化" + "设计")


def test_rouge_1():
    assert rouge_1("a b c", "a b d") == pytest.approx(2 / 3)


@pytest.mark.parametrize(("value", "expected"), [
    (3, 3.0), ("1,234.5", 1234.5), ("12%", 0.12), ("about 7.5 kg", 7.5), ("none", None),
    (True, None),
])
def test_parse_number(value, expected):
    assert parse_number(value) == expected


def test_numbers_match_follows_the_kramabench_success_rule():
    assert numbers_match("8577.5298", 8577.5298)
    assert numbers_match(8577.53, 8577.5298)  # rounding difference below 1e-4 of the magnitude
    assert not numbers_match(8600, 8577.5298)
    assert numbers_match(0.0, 0)
    assert not numbers_match("n/a", 1)


def test_list_f1():
    assert list_f1('["a.xlsx", "B.xlsx"]', ["A.xlsx", "b.xlsx"]) == 1.0
    assert list_f1("1, 2, 9", [1, 2, 3]) == pytest.approx(2 / 3)
    assert list_f1([], []) == 1.0
    assert list_f1([], [1]) == 0.0
