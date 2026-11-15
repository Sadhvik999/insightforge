
import pandas as pd
import pytest

from app.conversation_store import (
    CONVERSATIONS,
    create_conversation,
    get_conversation,
    update_conversation,
    delete_conversation
)


@pytest.fixture(autouse=True)
def clear_conversations():
    CONVERSATIONS.clear()
    yield
    CONVERSATIONS.clear()


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "City": ["Delhi", "Mumbai", "Delhi"],
        "Sales": [500, 800, 700]
    })


def test_create_conversation(sample_df):
    conversation_id = create_conversation(sample_df)

    assert conversation_id in CONVERSATIONS
    assert isinstance(conversation_id, str)
    assert CONVERSATIONS[conversation_id]["messages"] == []
    pd.testing.assert_frame_equal(
        CONVERSATIONS[conversation_id]["df"],
        sample_df
    )


def test_conversations_have_unique_ids(sample_df):
    first_id = create_conversation(sample_df)
    second_id = create_conversation(sample_df)

    assert first_id != second_id


def test_get_conversation(sample_df):
    conversation_id = create_conversation(sample_df)

    conversation = get_conversation(conversation_id)

    assert "df" in conversation
    assert "messages" in conversation


def test_get_unknown_conversation():
    with pytest.raises(ValueError, match="Conversation not found"):
        get_conversation("invalid-id")


def test_update_conversation(sample_df):
    conversation_id = create_conversation(sample_df)

    messages = [
        {"role": "user", "content": "Show total sales."}
    ]

    update_conversation(conversation_id, messages)

    conversation = get_conversation(conversation_id)

    assert conversation["messages"] == messages


def test_update_rejects_invalid_messages(sample_df):
    conversation_id = create_conversation(sample_df)

    with pytest.raises(ValueError, match="must be a list"):
        update_conversation(conversation_id, "invalid")


def test_delete_conversation(sample_df):
    conversation_id = create_conversation(sample_df)

    delete_conversation(conversation_id)

    assert conversation_id not in CONVERSATIONS


def test_delete_unknown_conversation():
    with pytest.raises(ValueError, match="Conversation not found"):
        delete_conversation("invalid-id")


def test_create_rejects_empty_dataframe():
    with pytest.raises(ValueError, match="empty dataset"):
        create_conversation(pd.DataFrame())


def test_create_rejects_non_dataframe():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        create_conversation([1, 2, 3])
