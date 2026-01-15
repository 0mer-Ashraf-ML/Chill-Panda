import streamlit as st
import requests
import uuid
import json

# -------------------------------
# Config
# -------------------------------
CHAT_API_URL = "http://localhost:8000/api/v1/chat"

st.set_page_config(
    page_title="Chill Panda Chat",
    page_icon="🐼",
    layout="centered"
)

st.title("🐼 Chill Panda Chat")
st.caption("Your calm, wise panda guide 🌿")

# -------------------------------
# User / Session
# -------------------------------
user_id = st.text_input("User ID", "test_user")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

session_id = st.session_state.session_id
st.caption(f"Session ID: `{session_id}`")

# -------------------------------
# Role Selection
# -------------------------------
ROLE_MAP = {
    "Loyal Best Friend 🐼": "best_friend",
    "Caring Parent 💛": "caring_parent",
    "Coach 🌱": "coach"
}

selected_role_label = st.selectbox(
    "Choose how Chill Panda should support you:",
    list(ROLE_MAP.keys())
)

selected_role = ROLE_MAP[selected_role_label]

# -------------------------------
# Display Chat History
# -------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------
# User Input
# -------------------------------
prompt = st.chat_input("Talk to Chill Panda...")

if prompt:
    # Show user message
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            with requests.post(
                CHAT_API_URL,
                json={
                    "session_id": session_id,
                    "user_id": user_id,
                    "input_text": prompt,
                    "language": "en",
                    "role": selected_role
                },
                stream=True,
                timeout=60
            ) as response:

                for line in response.iter_lines():
                    if not line:
                        continue

                    decoded = line.decode("utf-8")

                    if decoded.startswith("data:"):
                        payload = json.loads(
                            decoded.replace("data:", "").strip()
                        )

                        if not payload.get("is_end"):
                            chunk = payload.get("reply", "")
                            full_response += chunk
                            response_placeholder.markdown(full_response)

            # Save assistant message
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

        except Exception as e:
            st.error(f"Chat error: {e}")
