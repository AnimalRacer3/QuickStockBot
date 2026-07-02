import pytest

from trader.execution import ExecutionError, _find_order_record


def test_find_order_record_bare_dict_matching_id():
    payload = {"id": "abc123", "status": "filled", "filled_avg_price": 10.5}
    assert _find_order_record(payload, "abc123") == payload


def test_find_order_record_bare_list():
    payload = [
        {"id": "other", "status": "filled"},
        {"id": "abc123", "status": "filled", "filled_avg_price": 10.5},
    ]
    result = _find_order_record(payload, "abc123")
    assert result["id"] == "abc123"


def test_find_order_record_wrapped_list():
    payload = {"orders": [{"order_id": "abc123", "status": "pending"}]}
    result = _find_order_record(payload, "abc123")
    assert result["order_id"] == "abc123"


def test_find_order_record_not_found_raises():
    payload = {"orders": [{"id": "other", "status": "filled"}]}
    with pytest.raises(ExecutionError):
        _find_order_record(payload, "abc123")


def test_find_order_record_dict_without_id_falls_back_to_self():
    # A purpose-built single-order-status tool might not echo the id back.
    payload = {"status": "filled", "filled_avg_price": 10.5}
    assert _find_order_record(payload, "abc123") == payload
