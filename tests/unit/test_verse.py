from services.api.verse.service import diff_configurations, three_way_merge


def test_configuration_diff():
    diff = diff_configurations({"a": True, "b": 1, "gone": "x"}, {"a": False, "b": 1, "new": "y"})
    assert diff.added == {"new": "y"}
    assert diff.removed == {"gone": "x"}
    assert diff.changed == {"a": {"from": True, "to": False}}
    assert diff.unchanged_count == 1


def test_three_way_merge_and_conflict_detection():
    merged, conflicts = three_way_merge(
        {"theme": "light", "search": "basic"},
        {"theme": "dark", "search": "basic"},
        {"theme": "light", "search": "advanced"},
    )
    assert merged == {"search": "advanced", "theme": "dark"}
    assert conflicts == []

    _, conflicts = three_way_merge({"theme": "light"}, {"theme": "dark"}, {"theme": "system"})
    assert conflicts == [{"key": "theme", "ancestor": "light", "source": "dark", "destination": "system"}]
