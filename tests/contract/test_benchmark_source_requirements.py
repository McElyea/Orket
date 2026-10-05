"""Contract: entrypoint syntax accepts equivalent quotes and rejects text-only claims."""
import pytest

from scripts.benchmarks.live_card_benchmark_runner import _evaluate_quality
from scripts.benchmarks.source_requirements import MAIN_GUARD

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("source, expected", [
    ('if __name__ == "__main__":\n    print(1)', True),
    ("if __name__ == '__main__':\n    print(1)", True),
    ("if '__main__' == __name__:\n    print(1)", True),
    ('# if __name__ == "__main__":\nprint(1)', False),
    ('''text = 'if __name__ == "__main__":' ''', False),
    ('def unused():\n    if __name__ == "__main__":\n        print(1)', False),
    ('if __name__ != "__main__":\n    print(1)', False),
    ('if __name__ == "__main__" == other:\n    print(1)', False),
    ('if __name__ == "__main__":', False),
])
def test_quality_requires_real_top_level_main_guard(source, expected):
    task = {"acceptance_contract": {"mode": "module", "quality_required_keywords": [MAIN_GUARD]}}
    result = _evaluate_quality(task, source)
    check = next(row for row in result["checks"] if row["name"] == "required_keywords_present")
    assert check["passed"] is expected
