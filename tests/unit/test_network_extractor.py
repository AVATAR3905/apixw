"""Unit tests for network-layer extraction helpers (XHR payload archaeology)."""

from services.collectors.network_extractor import (
    collect_values,
    find_quote_candidates,
    truncate,
)


def test_collect_values_recurses_through_nested_rpc_payload():
    payload = {
        "proto": [[[[{"price": 100}], [{"price": 200}]], {"price": 300}]],
        "meta": {"price": 400},
    }
    found = collect_values(payload, "price")
    assert sorted(found) == [100, 200, 300, 400]


def test_collect_values_caps_at_max_hits():
    payload = {"v": [{"price": i} for i in range(50)]}
    assert len(collect_values(payload, "price", max_hits=10)) == 10


def test_find_quote_candidates_with_predicates():
    payload = {
        "response": [
            {"tracking_id": "abc", "price_display": "N/A"},
            {
                "origin": "DEL",
                "dest": "BOM",
                "fare": {"amount": 3540.0, "currency": "INR"},
                "flight": "6E-205",
            },
        ],
        "session": {"token": "xyz"},
    }

    def has_origin(node):
        return "origin" in node and "dest" in node

    def has_fare(node):
        return isinstance(node.get("fare"), dict)

    candidates = find_quote_candidates(payload, [has_origin, has_fare])
    assert len(candidates) == 1
    assert candidates[0]["flight"] == "6E-205"


def test_truncate_long_payloads():
    truncated = truncate("a" * 100, limit=20)
    assert "[truncated" in truncated
    assert len(truncated) < 100
    assert truncate("short") == "'short'"
