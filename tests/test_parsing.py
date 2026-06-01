import json

from reader_agent.tools import extract_references


def test_extract_references_basic():
    refs_text = """
[1] Smith, J. 2020. Paper One. ACL.
[2] Doe, A. 2021. Paper Two. EMNLP.
"""
    result = json.loads(extract_references.func(refs_text))
    assert result["count"] >= 2
    assert result["references"][0]["year"] in {"2020", "2021"}
