from grokprint.extract import _extract_need


def test_strong_should_i():
    text = "I fixed the tests.\n\nShould I push this branch for review?"
    need = _extract_need(text)
    assert need
    assert any("push" in n.lower() for n in need)


def test_rhetorical_what_is_not_need():
    text = (
        "Here is the design.\n"
        "What is a mutex? A lock that serializes access.\n"
        "What does the scheduler do? It picks a runnable task.\n"
        "All claims backed by the source."
    )
    need = _extract_need(text)
    assert need == []


def test_code_fence_question_ignored():
    text = (
        "Updated the parser.\n"
        "```python\n"
        "# why does this fail?\n"
        "x = 1\n"
        "```\n"
        "Done."
    )
    need = _extract_need(text)
    assert need == []


def test_just_do_it_no_false_need():
    text = (
        "Applied the rename across 12 files and re-ran unit tests (all green).\n"
        "Committed on branch feat/rename."
    )
    assert _extract_need(text) == []


def test_multi_decision_questions():
    text = (
        "Two open choices:\n"
        "1. Do you want Postgres or SQLite for local dev?\n"
        "2. Should I open a draft PR or wait?\n"
    )
    need = _extract_need(text)
    assert len(need) >= 2


def test_weak_you_question_counts():
    text = "The migration is ready.\n\nAre you ok with downtime during deploy?"
    need = _extract_need(text)
    assert need
    assert any("downtime" in n.lower() or "deploy" in n.lower() for n in need)
