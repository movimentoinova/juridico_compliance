import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import redis
import uuid
import base64
import json  # To store complex objects like lists in Redis

# Load environment variables
load_dotenv()

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Generate a unique session ID for each new session
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

# Cache chat history to avoid reloading frequently, set TTL to limit stale data
@st.cache_data(ttl=60)
def load_chat_history(session_id):
    chat_data = redis_client.get(session_id)
    if chat_data:
        return json.loads(chat_data)
    return []

def save_chat_history(session_id, messages):
    redis_client.set(session_id, json.dumps(messages))

# Cache global history for the sidebar, limiting the number of messages to load
@st.cache_data(ttl=60)
def load_recent_global_history(limit=50):
    global_history_data = redis_client.get("history_messages")
    if global_history_data:
        return json.loads(global_history_data)[-limit:]  # Load only last 'limit' messages
    return []

def save_global_history(history_messages):
    redis_client.set("history_messages", json.dumps(history_messages))

# Load chat history only once and store in session state
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state["session_id"])

# Load global history for sidebar, limiting messages
if "history_messages" not in st.session_state:
    st.session_state.history_messages = load_recent_global_history()

# Function to append new conversation to the history
def append_to_history(new_messages):
    st.session_state.history_messages.extend(new_messages)
    save_global_history(st.session_state.history_messages)

# This system message is used for setting the assistant's behavior
system_message = {"role": "system", "content": os.getenv("JURIDICO_COMPLIANCE_SYSTEM_MESSAGE")}

# Cache the PNG file loading to avoid re-reading the file
@st.cache_resource
def get_image_as_base64(image_file_path):
    with open(image_file_path, "rb") as file:
        image_content = file.read()
    return base64.b64encode(image_content).decode('utf-8')

# Path to your local PNG image file
image_file_path = "background.png"

# Convert the PNG file to base64
image_base64 = get_image_as_base64(image_file_path)

# Sidebar history and chat navigation with lazy loading
with st.sidebar:
    st.header("Histórico de Conversas")
    
    if st.button("Nova Conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())

    # Group and display recent conversations
    conversations = []
    current_conversation = []
    for message in st.session_state.history_messages:
        current_conversation.append(message)
        if message['role'] == 'assistant':
            conversations.append(current_conversation)
            current_conversation = []
    if current_conversation:
        conversations.append(current_conversation)

    # Reverse to display the most recent first
    for i, conversation in enumerate(reversed(conversations)):
        user_messages = [msg for msg in conversation if msg['role'] == 'user']
        if user_messages:
            first_user_message = user_messages[0]['content']
            truncated_message = first_user_message[:50] + "..." if len(first_user_message) > 50 else first_user_message
            if st.button(truncated_message, key=f"load_{i}", use_container_width=True):
                st.session_state.messages = conversation
                # No need to rerun; updating session state directly

# Background with more efficient image format
st.markdown(
    f"""
    <style>
    html, body {{
        height: 100%;
        margin: 0;
        padding: 0;
    }}
    
    body {{
        background-image: url('data:image/png;base64,{image_base64}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}

    [data-testid="stAppViewContainer"] {{
        padding: 0 !important;
        height: 100vh;
    }}

    [data-testid="stHeader"], [data-testid="stToolbar"] {{
        display: none;
    }}
    
    .stButton > button {{
        width: 100%;
        border: 1px solid #ccc;
        background-color: #2F3136;
        color: rgba(255, 255, 255, 1);
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
        justify-content: flex-start;
        align-items: center;
        text-align: left;
    }}
    </style>
    """, unsafe_allow_html=True
)

# Lazy loading conversation messages to reduce initial load time
MAX_MESSAGES = 10  # Display a limited number of messages initially
displayed_messages = st.session_state.messages[-MAX_MESSAGES:]
for message in displayed_messages:
    avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

if len(st.session_state.messages) > MAX_MESSAGES:
    if st.button("Load More Messages"):
        displayed_messages = st.session_state.messages
        for message in displayed_messages:
            avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

# Main chat interface
if prompt := st.chat_input("Como eu posso te ajudar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        message_placeholder = st.empty()
        full_response = ""
        conversation_history = [system_message] + st.session_state["messages"]
        for response in client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=conversation_history,
            stream=True,
        ):
            full_response += response.choices[0].delta.content or ""
            message_placeholder.markdown(full_response + "|")
        message_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Append new messages to the global history
    append_to_history(st.session_state.messages)

# Save chat and history after each interaction
save_chat_history(st.session_state["session_id"], st.session_state.messages)
