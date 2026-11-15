
import uuid
import pandas as pd


# In-memory storage for active conversations.
CONVERSATIONS = {}


def create_conversation(df):
    """
    Create a new conversation and store its dataset.
    """

    if not isinstance(df, pd.DataFrame):
        raise ValueError("Dataset must be a pandas DataFrame.")

    if df.empty:
        raise ValueError("Cannot create a conversation with an empty dataset.")

    conversation_id = str(uuid.uuid4())

    CONVERSATIONS[conversation_id] = {
        "df": df.copy(),
        "messages": []
    }

    return conversation_id


def get_conversation(conversation_id):
    """
    Retrieve an existing conversation.
    """

    conversation = CONVERSATIONS.get(conversation_id)

    if conversation is None:
        raise ValueError("Conversation not found.")

    return conversation


def update_conversation(conversation_id, messages):
    """
    Update the conversation's message history.
    """

    conversation = get_conversation(conversation_id)

    if not isinstance(messages, list):
        raise ValueError("Conversation messages must be a list.")

    conversation["messages"] = messages


def delete_conversation(conversation_id):
    """
    Delete a conversation and its stored dataset.
    """

    if conversation_id not in CONVERSATIONS:
        raise ValueError("Conversation not found.")

    del CONVERSATIONS[conversation_id]
