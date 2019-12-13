# coding: utf-8
"""
Tests for builders
"""
import pytest
from datetime import datetime, timedelta

from maggma.stores import MemoryStore
from maggma.builders import CopyBuilder


@pytest.fixture
def source():
    store = MemoryStore("source", key="k", last_updated_field="lu")
    store.connect()
    store.ensure_index("k")
    store.ensure_index("lu")
    return store


@pytest.fixture
def target():
    store = MemoryStore("target", key="k", last_updated_field="lu")
    store.connect()
    store.ensure_index("k")
    store.ensure_index("lu")
    return store


@pytest.fixture("module")
def now():
    return datetime.utcnow()


@pytest.fixture
def old_docs(now):
    return [{"lu": now, "k": k, "v": "old"} for k in range(20)]


@pytest.fixture
def new_docs(now):
    toc = now + timedelta(seconds=1)
    return [{"lu": toc, "k": k, "v": "new"} for k in range(0, 10)]


def test_get_items(source, target, old_docs):
    builder = CopyBuilder(source, target)
    source.update(old_docs)
    assert len(list(builder.get_items())) == len(old_docs)
    target.update(old_docs)
    assert len(list(builder.get_items())) == 0


def test_process_item(source, target, old_docs):
    builder = CopyBuilder(source, target)
    source.update(old_docs)
    items = list(builder.get_items())
    assert len(items) == len(list(map(builder.process_item, items)))


def test_update_targets(source, target, old_docs, new_docs):
    builder = CopyBuilder(source, target)
    builder.update_targets(old_docs)
    builder.update_targets(new_docs)
    assert target.query_one(criteria={"k": 0})["v"] == "new"
    assert target.query_one(criteria={"k": 10})["v"] == "old"


def test_run(source, target, old_docs, new_docs):
    source.update(old_docs)
    source.update(new_docs)
    target.update(old_docs)

    builder = CopyBuilder(source, target)
    builder.run()
    assert target.query_one(criteria={"k": 0})["v"] == "new"
    assert target.query_one(criteria={"k": 10})["v"] == "old"


def test_query(source, target, old_docs, new_docs):
    builder = CopyBuilder(source, target)
    builder.query = {"k": {"$gt": 5}}
    source.update(old_docs)
    source.update(new_docs)
    builder.run()
    all_docs = list(target.query(criteria={}))
    assert len(all_docs) == 14
    assert min([d["k"] for d in all_docs]) == 6


def test_delete_orphans(source, target, old_docs, new_docs):
    builder = CopyBuilder(source, target, delete_orphans=True)
    source.update(old_docs)
    source.update(new_docs)
    target.update(old_docs)

    deletion_criteria = {"k": {"$in": list(range(5))}}
    source.collection.delete_many(deletion_criteria)
    builder.run()

    assert target.collection.count_documents(deletion_criteria) == 0
    assert target.query_one(criteria={"k": 5})["v"] == "new"
    assert target.query_one(criteria={"k": 10})["v"] == "old"


def test_prechunk(source, target, old_docs, new_docs):
    builder = CopyBuilder(source, target, delete_orphans=True)
    source.update(old_docs)
    source.update(new_docs)

    chunk_queries = list(builder.prechunk(2))
    assert len(chunk_queries) == 2
    assert chunk_queries[0] == {"k": {"$in": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}}
