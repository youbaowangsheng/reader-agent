from app.service.citation import validate_citations


def _retrieved_map():
    return {
        "doc_x_c0001": "The method significantly improves recall under noisy conditions.",
        "doc_x_c0002": "Ablation shows the gain drops when memory module is removed.",
    }


def test_validate_citations_pass():
    cites = [
        {"chunk_id": "doc_x_c0001", "quote": "improves recall under noisy conditions"},
        {"chunk_id": "doc_x_c0002", "quote": "gain drops when memory module is removed"},
    ]
    assert validate_citations(cites, _retrieved_map(), min_required=2) is True


def test_validate_citations_fail_on_count_or_quote():
    bad_count = [{"chunk_id": "doc_x_c0001", "quote": "improves recall under noisy conditions"}]
    bad_quote = [
        {"chunk_id": "doc_x_c0001", "quote": "totally unrelated"},
        {"chunk_id": "doc_x_c0002", "quote": "gain drops when memory module is removed"},
    ]
    assert validate_citations(bad_count, _retrieved_map(), min_required=2) is False
    assert validate_citations(bad_quote, _retrieved_map(), min_required=2) is False
