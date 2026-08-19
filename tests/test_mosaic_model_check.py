from benchmarks.model_check_mosaic import run_checks


def test_bounded_mosaic_model_check_passes():
    result = run_checks()
    assert result["passed"] is True
    assert all(item["passed"] for item in result["results"])
