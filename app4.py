import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import redis
import uuid
import base64
import json
from datetime import datetime

# Load environment variables
load_dotenv()

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Connect to Redis with error handling
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
except redis.ConnectionError as e:
    st.error(f"Error connecting to Redis: {e}")
    st.stop()

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "openai_model" not in st.session_state:
    st.session_state.openai_model = "gpt-4o-mini"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "loaded_sessions" not in st.session_state:
    st.session_state.loaded_sessions = {}  # Cache loaded chat sessions
if "selected_session_id" not in st.session_state:
    st.session_state.selected_session_id = None  # Track selected chat
if "displayed_messages_count" not in st.session_state:
    st.session_state.displayed_messages_count = 10  # Control how many messages to load

# This system message is used for setting the assistant's behavior
system_message = {"role": "system", "content": os.getenv("JURIDICO_COMPLIANCE_SYSTEM_MESSAGE")}

# Function to load chat history from Redis and cache it in session_state
def load_chat_history(session_id):
    if session_id not in st.session_state.loaded_sessions:
        try:
            chat_data = redis_client.get(session_id)
        except redis.RedisError as e:
            st.error(f"Error loading chat history from Redis: {e}")
            return []
        if chat_data:
            st.session_state.loaded_sessions[session_id] = json.loads(chat_data)
        else:
            st.session_state.loaded_sessions[session_id] = []
    return st.session_state.loaded_sessions[session_id]

# Function to save chat history to Redis with error handling
def save_chat_history(session_id, messages):
    try:
        redis_client.set(session_id, json.dumps(messages))
    except redis.RedisError as e:
        st.error(f"Error saving chat history to Redis: {e}")

# Function to load chat sessions (metadata)
def load_chat_sessions():
    try:
        sessions = redis_client.smembers("chat_sessions")
        return [json.loads(s) for s in sessions]
    except redis.RedisError as e:
        st.error(f"Error loading chat sessions: {e}")
        return []

# Function to save chat session metadata with error handling
def save_chat_session(session_id, first_message, timestamp):
    session_data = json.dumps({"id": session_id, "first_message": first_message, "timestamp": timestamp})
    try:
        redis_client.sadd("chat_sessions", session_data)
    except redis.RedisError as e:
        st.error(f"Error saving chat session metadata: {e}")

# Function to encode the image in base64
def get_image_as_base64(image_file_path):
    with open(image_file_path, "rb") as file:
        image_content = file.read()
    return base64.b64encode(image_content).decode('utf-8')

# Path to your local PNG image file
image_file_path = "background.png"
image_base64 = get_image_as_base64(image_file_path)

# Always render background first to ensure it persists across reruns
st.markdown(f"""
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
        background-color: #3e4147;
        color: rgba(255, 255, 255, 1);
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
        justify-content: flex-start;
        align-items: center;
        text-align: left;
    }}
    </style>
""", unsafe_allow_html=True)

# Sidebar for chat history
with st.sidebar:
    st.header("Histórico de Conversas")
    
    if st.button("Nova Conversa", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.selected_session_id = st.session_state.session_id  # Set as selected
        st.session_state.displayed_messages_count = 10  # Reset message count

    # Load and display chat sessions
    chat_sessions = load_chat_sessions()
    for session in sorted(chat_sessions, key=lambda x: x['timestamp'], reverse=True):
        button_label = f"{session['first_message'][:50]}..."
        if st.button(button_label, key=session['id'], use_container_width=True):
            # Only update the session state without causing a rerun
            st.session_state.selected_session_id = session['id']
            st.session_state.messages = load_chat_history(session['id'])
            st.session_state.displayed_messages_count = 10  # Reset for this session

# Display chat messages with pagination
if st.session_state.selected_session_id:
    displayed_messages = st.session_state.messages[-st.session_state.displayed_messages_count:]
    for message in displayed_messages:
        with st.chat_message(message["role"], avatar=USER_AVATAR if message["role"] == "user" else BOT_AVATAR):
            st.markdown(message["content"])

    if len(st.session_state.messages) > st.session_state.displayed_messages_count:
        if st.button("Carregar Mais Mensagens"):
            st.session_state.displayed_messages_count += 10  # Load 10 more messages

# Chat input is now always visible regardless of selected session
prompt = st.chat_input("Como eu posso te ajudar hoje?")

# Process user input and chat response only if there's a prompt
if prompt:
    # Ensure a session is created if none exists
    if not st.session_state.selected_session_id:
        st.session_state.selected_session_id = st.session_state.session_id
        st.session_state.messages = []

    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    # Generate assistant response with error handling
    try:
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model=st.session_state.openai_model,
                messages=[system_message] + st.session_state.messages,
                stream=True,
            ):
                full_response += (response.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
    except Exception as e:
        st.error(f"Error generating response from OpenAI: {e}")

    # Save chat history
    save_chat_history(st.session_state.selected_session_id, st.session_state.messages)

    # Save chat session if it's a new conversation
    if len(st.session_state.messages) == 2:  # First user message and first assistant response
        save_chat_session(st.session_state.selected_session_id, prompt, str(datetime.now()))