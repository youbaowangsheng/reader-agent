from app.schema.note import OverallEvaluation


def test_overall_evaluation_defaults():
    obj = OverallEvaluation()
    assert obj.novelty == 3
    assert obj.rigor == 3
    assert obj.reproducibility == 3
    assert obj.recommendation
