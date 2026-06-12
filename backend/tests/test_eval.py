from app.eval.deepeval_runner import check_citations_present


def test_citations_check():
    result = check_citations_present(
        {"citations": [{"snippet": "test"}], "memo_markdown": "long memo"}
    )
    assert result["status"] == "passed"
    assert result["citation_count"] == 1
