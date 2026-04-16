from datetime import datetime

from keiba_ai.data.schema import (
    BetRecommendation,
    Prediction,
    Race,
    RacePrediction,
    RunningStyle,
    Surface,
    TicketType,
    TrackCondition,
    TurnDirection,
)


def test_race_schema():
    r = Race(
        race_id="R001", date=datetime(2024, 1, 1, 10, 0),
        course="東京", race_no=1, distance_m=1600, surface=Surface.TURF,
        turn=TurnDirection.LEFT, track_condition=TrackCondition.FIRM,
        n_runners=16, post_time=datetime(2024, 1, 1, 10, 30),
    )
    assert r.race_id == "R001"
    assert r.surface == Surface.TURF


def test_prediction_roundtrip():
    p = Prediction(
        race_id="R001", horse_no=3, horse_name="テスト",
        score=1.2, p_win=0.25, p_2nd=0.2, p_3rd=0.15, p_place=0.6,
        running_style=RunningStyle.SENKO,
    )
    d = p.model_dump()
    p2 = Prediction(**d)
    assert p2.p_win == 0.25


def test_bet_recommendation():
    bet = BetRecommendation(
        ticket=TicketType.WIN, selection="3", odds=3.5,
        probability=0.35, expected_value=0.225, kelly_fraction=0.09, stake=300,
    )
    assert bet.ticket == TicketType.WIN
