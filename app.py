import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import shelve
import uuid
import base64

load_dotenv()

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Generate a unique session ID for each new session
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

# Load chat history from shelve file based on session ID
def load_chat_history(session_id):
    with shelve.open("chat_history") as db:
        return db.get(session_id, [])

# Save chat history to shelve file based on session ID
def save_chat_history(session_id, messages):
    with shelve.open("chat_history") as db:
        db[session_id] = messages

# Initialize or load chat history
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state["session_id"])

# This system message is used for setting the assistant's behavior
system_message = {"role": "system", "content": os.getenv("JURIDICO_COMPLIANCE_SYSTEM_MESSAGE")}

# Read the SVG file and convert it to base64
def get_svg_as_base64(svg_file_path):
    with open(svg_file_path, "r") as file:
        svg_content = file.read()
    return base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')

# Path to your local SVG file
svg_file_path = "image.svg"

# Convert the SVG file to base64
svg_base64 = get_svg_as_base64(svg_file_path)

st.markdown(
    f"""
    <style>
    html, body {{
        height: 100%;
        margin: 0;
        padding: 0;
    }}
    
    body {{
        background-image: url('data:image/svg+xml;base64,{svg_base64}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}

    [data-testid="stAppViewContainer"] {{
        padding: 0 !important;
        height: 100vh;
    }}

    [data-testid="stHeader"] {{
        display: none;
    }}

    [data-testid="stToolbar"] {{
        display: none;
    }}

    </style>
    """, unsafe_allow_html=True
)


# Display chat messages
for message in st.session_state.messages:
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

# Save chat history after each interaction
save_chat_history(st.session_state["session_id"], st.session_state.messages)

