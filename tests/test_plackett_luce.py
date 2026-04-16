import numpy as np

from keiba_ai.models.plackett_luce import (
    exacta_prob,
    finish_probabilities,
    quinella_prob,
    trifecta_prob,
    trio_prob,
)


def test_probabilities_sum_to_one():
    scores = np.array([2.0, 1.0, 0.5, -0.3, -1.2, -2.0])
    fp = finish_probabilities(scores)
    # P(1着) 合計は厳密に1
    assert abs(fp["p1"].sum() - 1.0) < 1e-9
    # P(2着), P(3着) も合計は1（Plackett-Luceの期待値）
    assert abs(fp["p2"].sum() - 1.0) < 1e-6
    assert abs(fp["p3"].sum() - 1.0) < 1e-6
    # 各馬の place = p1+p2+p3 は定義通り
    np.testing.assert_allclose(fp["place"], fp["p1"] + fp["p2"] + fp["p3"])
    # place 合計は 3（1+2+3位が1馬ずつ埋まるため）
    assert abs(fp["place"].sum() - 3.0) < 1e-6


def test_exacta_and_quinella_consistency():
    scores = np.array([1.5, 0.8, 0.2, -0.5])
    # 馬単の sum は 1
    total = 0.0
    for i in range(4):
        for j in range(4):
            if i == j:
                continue
            total += exacta_prob(scores, i, j)
    assert abs(total - 1.0) < 1e-6
    # 馬連は i<j のペア合計で 1
    qsum = sum(quinella_prob(scores, i, j) for i in range(4) for j in range(i + 1, 4))
    assert abs(qsum - 1.0) < 1e-6


def test_trifecta_trio():
    scores = np.array([1.5, 0.8, 0.2, -0.5, -1.1])
    tf = 0.0
    for i in range(5):
        for j in range(5):
            for k in range(5):
                if len({i, j, k}) < 3:
                    continue
                tf += trifecta_prob(scores, i, j, k)
    assert abs(tf - 1.0) < 1e-6
    # 3連複: C(5,3)=10 組合計で 1
    from itertools import combinations
    tr = sum(trio_prob(scores, *c) for c in combinations(range(5), 3))
    assert abs(tr - 1.0) < 1e-6


def test_top_horse_has_highest_p_win():
    scores = np.array([0.2, 0.1, 0.9, 0.3])
    fp = finish_probabilities(scores)
    assert int(np.argmax(fp["p1"])) == 2
