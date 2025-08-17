import pytest
from unittest.mock import MagicMock

from engine.conversation_store import ConversationStore, DEFAULT_CATEGORY


def test_list_conversation_meta_success():
    adapter = MagicMock()
    adapter.list_conversation_meta.return_value = [{"id": "1", "title": "t"}]
    store = ConversationStore(db=adapter)

    res = store.list_conversation_meta("user1")

    adapter.list_conversation_meta.assert_called_once_with(user_id="user1", category=DEFAULT_CATEGORY)
    assert res == [{"id": "1", "title": "t"}]


def test_list_conversation_meta_no_user_returns_empty():
    adapter = MagicMock()
    store = ConversationStore(db=adapter)

    res = store.list_conversation_meta("", DEFAULT_CATEGORY)

    assert res == []


def test_load_conversation_existing_applies_defaults():
    adapter = MagicMock()
    adapter.load_conversation.return_value = {"history": [{"role": "user", "content": "hi"}]}
    store = ConversationStore(db=adapter)

    res = store.load_conversation("c1", "u1")

    adapter.load_conversation.assert_called_once_with(user_id="u1", conversation_id="c1")
    assert res["history"] == [{"role": "user", "content": "hi"}]
    assert res["category"] == DEFAULT_CATEGORY
    assert res["mode"] == "normal"
    assert res["project_path"] is None


def test_load_conversation_not_found_returns_none():
    adapter = MagicMock()
    adapter.load_conversation.return_value = None
    store = ConversationStore(db=adapter)

    res = store.load_conversation("c1", "u1")

    assert res is None


def test_load_conversation_requires_user_id():
    store = ConversationStore(db=MagicMock())
    with pytest.raises(ValueError):
        store.load_conversation("c1", "")


def test_save_conversation_success():
    adapter = MagicMock()
    adapter.save_conversation.return_value = True
    store = ConversationStore(db=adapter)

    data = {"history": []}
    ok = store.save_conversation("c1", data, "u1")

    assert ok is True
    adapter.save_conversation.assert_called_once()
    kwargs = adapter.save_conversation.call_args.kwargs
    assert kwargs["user_id"] == "u1"
    assert kwargs["conversation_id"] == "c1"
    assert kwargs["data"]["category"] == DEFAULT_CATEGORY


def test_save_conversation_handles_error_returns_false():
    adapter = MagicMock()
    adapter.save_conversation.side_effect = Exception("db fail")
    store = ConversationStore(db=adapter)

    ok = store.save_conversation("c1", {"history": []}, "u1")

    assert ok is False


def test_save_conversation_requires_user_id():
    store = ConversationStore(db=MagicMock())
    with pytest.raises(ValueError):
        store.save_conversation("c1", {"history": []}, "")


def test_create_new_conversation_calls_adapter_with_defaults():
    adapter = MagicMock()
    adapter.create_new_conversation.return_value = "newid"
    store = ConversationStore(db=adapter)

    cid = store.create_new_conversation("u1")

    assert cid == "newid"
    adapter.create_new_conversation.assert_called_once_with(user_id="u1", title="New Conversation", category=DEFAULT_CATEGORY)
