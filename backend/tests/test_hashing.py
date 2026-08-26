import math

import pytest

from devstacks_domain import canonical_json, content_hash


def test_canonical_json_sorts_object_keys_recursively():
    left = {"repository": {"name": "devstacks", "owner": "padal"}, "pr": 42}
    right = {"pr": 42, "repository": {"owner": "padal", "name": "devstacks"}}

    assert canonical_json(left) == canonical_json(right)
    assert content_hash(left) == content_hash(right)


def test_content_hash_changes_when_observed_content_changes():
    original = {"commits": 7, "repository": "devstacks"}
    changed = {"commits": 8, "repository": "devstacks"}

    assert content_hash(original) != content_hash(changed)


def test_canonical_json_rejects_non_json_numeric_values():
    with pytest.raises(ValueError):
        canonical_json({"score": math.nan})