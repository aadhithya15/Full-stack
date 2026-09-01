"""Phase V2-1 tests - product catalogue query layer (Supabase mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from app.db import queries


@pytest.fixture()
def sb():
    with patch("app.db.queries.get_supabase") as m:
        client = MagicMock()
        m.return_value = client
        yield client


def _table_result(client, data, count=None):
    chain = client.table.return_value
    for method in ("select", "eq", "limit", "insert", "update", "upsert", "order"):
        getattr(chain, method).return_value = chain
    result = MagicMock()
    result.data = data
    result.count = count
    chain.execute.return_value = result
    return chain


def test_get_or_create_client_finds_existing(sb):
    _table_result(sb, [{"id": "c1", "name": "starter"}])
    row = queries.get_or_create_client("starter")
    assert row["id"] == "c1"


def test_get_or_create_client_creates_when_missing(sb):
    chain = sb.table.return_value
    for method in ("select", "eq", "limit", "insert"):
        getattr(chain, method).return_value = chain
    empty = MagicMock(); empty.data = []
    created = MagicMock(); created.data = [{"id": "c2", "name": "new-shop"}]
    chain.execute.side_effect = [empty, created]
    row = queries.get_or_create_client("new-shop")
    assert row["id"] == "c2"
    chain.insert.assert_called_once_with({"name": "new-shop"})


def test_upsert_product_inserts_new(sb):
    chain = sb.table.return_value
    for method in ("select", "eq", "limit", "insert", "update"):
        getattr(chain, method).return_value = chain
    empty = MagicMock(); empty.data = []
    inserted = MagicMock(); inserted.data = [{"id": "p1", "title": "Saree"}]
    chain.execute.side_effect = [empty, inserted]
    row = queries.upsert_product("c1", {"title": "Saree", "gender": "female"})
    assert row["id"] == "p1"
    args = chain.insert.call_args[0][0]
    assert args["client_id"] == "c1"


def test_upsert_product_updates_existing(sb):
    chain = sb.table.return_value
    for method in ("select", "eq", "limit", "insert", "update"):
        getattr(chain, method).return_value = chain
    existing = MagicMock(); existing.data = [{"id": "p9"}]
    updated = MagicMock(); updated.data = [{"id": "p9", "title": "Saree"}]
    chain.execute.side_effect = [existing, updated]
    row = queries.upsert_product("c1", {"title": "Saree"})
    assert row["id"] == "p9"
    chain.update.assert_called_once()


def test_search_products_calls_rpc_with_filters(sb):
    rpc_result = MagicMock()
    rpc_result.data = [{"id": "p1", "title": "Maroon Saree", "similarity": 0.91}]
    sb.rpc.return_value.execute.return_value = rpc_result

    vec = [0.1] * 512
    hits = queries.search_products_by_vector(
        vec, gender="female", culture="tamil", occasion="festive", limit=5
    )
    assert hits[0]["similarity"] == 0.91
    name, payload = sb.rpc.call_args[0]
    assert name == "match_products"
    assert payload["match_count"] == 5
    assert payload["filter_gender"] == "female"
    assert payload["filter_culture"] == "tamil"
    assert payload["filter_occasion"] == "festive"
    assert len(payload["query_embedding"]) == 512


def test_search_products_returns_empty_on_no_data(sb):
    rpc_result = MagicMock(); rpc_result.data = None
    sb.rpc.return_value.execute.return_value = rpc_result
    assert queries.search_products_by_vector([0.0] * 512) == []


def test_count_products(sb):
    _table_result(sb, [], count=42)
    assert queries.count_products() == 42
