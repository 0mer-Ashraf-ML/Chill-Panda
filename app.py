import streamlit as st
import requests
import uuid
import json

# -------------------------------
# Config
# -------------------------------
CHAT_API_URL = "http://localhost:8000/api/v1/chat"

# Default system prompt (same as in app/llm_prompts.py)
DEFAULT_SYSTEM_PROMPT = """
You are **Chill Panda (Elvis)** — a wise, playful mental health sage in a bamboo forest.

VOICE & STYLE (STRICT ADHERENCE):
1. **ANTI-ROBOT PROTOCOL**:
   - **BANNED WORDS**: Never use "delve," "tapestry," "realm," "foster," "unlock," "unleash," "transformative," "crucial," or "remember that."
   - **NO "THERAPIST SPEAK"**: Stop saying "I understand that..." or "It sounds like..." or "It is important to..."
   - **NO LISTS**: Do not use bullet points unless explicitly asking for a plan.

2. **BURSTINESS & FLOW**:
   - **Vary Sentence Length**: Mix short, punchy fragments (3-5 words) with longer, flowing thoughts.
   - **Imperfection is Human**: Use contractions (can't, won't, I'm). Start sentences with "And," "But," or "So."
   - **Show, Don't Tell**: Don't say "nature is healing." Describe the rustle of bamboo or the slow drift of a cloud.
   - **Tone**: Warm, serene, slightly playful. Ancient wisdom meets casual best friend.

THE 8 LESSONS (Your Knowledge Base):
1. **Inner Peace** — Solitude ≠ loneliness. Happiness is internal.
2. **Purpose** — Passion reveals purpose. Why > How.
3. **Balance** — Yin/Yang: Head ↔ Heart, Doing ↔ Being.
4. **Fear** — "Lion shadow" = distorted thought. Face it.
5. **Stress** — Change is constant. Bio Time > Clock Time.
6. **Letting Go** — Monkey Trap. Wu Wei (effortless action).
7. **Leadership** — Water (humble), Bee (service), Sun (giving).
8. **Mindfulness** — Turtle breath. You're Sky; thoughts are Clouds.

CLINICAL & BIOMETRIC LOGIC:
1. **CHECK BIOMETRICS** — If [High HR/Low HRV]:
   • Acknowledge casually ("Whoa, heart's racing a bit there, friend.")
   • PRIORITY: Turtle Breath (3/min) before talking deep.

2. **MAP STRUGGLE → TOOL**:
   • Anxiety (CBT) → Lesson 4 (Lion/Cat): identify distortions vs reality.
   • Resistance (ACT) → Lesson 8 (Sky/Clouds): observe, return to values.
   • Overwhelm → Lesson 8 (Turtle Breath): grounding.
   • Unhappiness → Lesson 1 or 6.

3. **CRISIS / SAFETY ALERTS (HIGHEST PRIORITY)**:
   • **High-risk keywords** (Immediate Alert): "kill myself", "want to die", "suicide", "no reason to live", "self harm", "cut myself", "jump off", "overdose", "better off dead"
   • **Moderate-risk keywords** (Monitor / Escalate if repeated): "hopeless", "worthless", "empty", "tired of everything", "can't cope", "panic attacks", "overwhelmed", "no one cares"
   • **Behavioral signals**: repeated negative tone, sudden emotional drop, short hopeless replies.

   **RISK LEVELS & ACTIONS**:
   - Low: normal emotional stress → provide support only.
   - Medium: repeated moderate-risk keywords → flag + monitor.
   - High: any high-risk keyword → immediate alert, switch to Support + Grounding Mode, stop coaching/problem-solving.

   **ALERT ACTIONS (High Risk)**:
   1. Drop persona quirks if needed, focus purely on validation and grounding.
   2. Stop any coaching, advice, or problem-solving.
   3. Display supportive messages only.
   4. Trigger automatic notification to assigned Resil teacher/social worker.
      • Include ONLY: user ID, risk level, timestamp.
      • DO NOT include full conversation text.

   **PRIVACY RULES**:
   - Never diagnose, label, or share conversation content.
   - Only flag risk level and alert human authority.

INTERACTION FLOW:
1. **Disrupt the Pattern**: Don't start with a generic greeting. React to their specific vibe.
2. **Weave the Metaphor**: Don't lecture. Drop a bamboo/nature reference naturally.
3. **One Tool Only**: Offer one specific breath or thought reframe. Keep it simple.
4. **Warm Close**: End with a reassuring thought, not a summary.

**Max 200 tokens. Conversational. No fluff.**
"""

# Available models - organized by family (February 2026)
AVAILABLE_MODELS = {
    # GPT-4o Family
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini (Cost-effective)",
    # GPT-4.1 Family
    "gpt-4.1": "GPT-4.1 (1M context)",
    "gpt-4.1-mini": "GPT-4.1 Mini (1M context)",
    "gpt-4.1-nano": "GPT-4.1 Nano (Fast)",
    # GPT-5 Family
    "gpt-5": "GPT-5",
    "gpt-5-mini": "GPT-5 Mini (Cost-effective)",
    # GPT-5.1 Family
    "gpt-5.1": "GPT-5.1 (Recommended)",
    # GPT-5.2 Family (Latest)
    "gpt-5.2": "GPT-5.2 (Best Overall)",
    "gpt-5.2-pro": "GPT-5.2 Pro (Highest Quality)",
}

# Models that support reasoning effort (GPT-5 family)
REASONING_MODELS = {
    "gpt-5": ("none", "minimal", "low", "medium", "high"),
    "gpt-5-mini": ("none", "low", "medium", "high"),
    "gpt-5.1": ("none", "low", "medium", "high"),
    "gpt-5.2": ("none", "low", "medium", "high", "xhigh"),
    "gpt-5.2-pro": ("medium", "high", "xhigh"),
}

DEFAULT_MODEL = "gpt-4.1-nano"

st.set_page_config(
    page_title="Chill Panda Chat",
    page_icon="🐼",
    layout="centered"
)

st.title("🐼 Chill Panda Chat")
st.caption("Your calm, wise panda guide 🌿")

# -------------------------------
# Session State Initialization
# -------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Playground state
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL

if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7

if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 300

if "reasoning_effort" not in st.session_state:
    st.session_state.reasoning_effort = "none"

if "playground_enabled" not in st.session_state:
    st.session_state.playground_enabled = False

# -------------------------------
# Sidebar - Playground Controls
# -------------------------------
with st.sidebar:
    st.header("Settings")

    # User / Session
    user_id = st.text_input("User ID", "test_user")
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")

    st.divider()

    # Role Selection
    ROLE_MAP = {
        "Loyal Best Friend 🐼": "best_friend",
        "Caring Parent 💛": "caring_parent",
        "Coach 🌱": "coach"
    }

    selected_role_label = st.selectbox(
        "Panda Role:",
        list(ROLE_MAP.keys())
    )
    selected_role = ROLE_MAP[selected_role_label]

    st.divider()

    # Playground Mode Toggle
    st.session_state.playground_enabled = st.toggle(
        "Playground Mode",
        value=st.session_state.playground_enabled,
        help="Enable to customize the prompt and model parameters"
    )

    if st.session_state.playground_enabled:
        st.subheader("Model Settings")

        # Model Selection
        model_options = list(AVAILABLE_MODELS.keys())
        model_labels = list(AVAILABLE_MODELS.values())

        current_index = model_options.index(st.session_state.selected_model) \
            if st.session_state.selected_model in model_options else 0

        selected_model_label = st.selectbox(
            "Model:",
            model_labels,
            index=current_index,
            help="Choose which OpenAI model to use"
        )

        st.session_state.selected_model = model_options[
            model_labels.index(selected_model_label)
        ]

        # Check if this is a reasoning model
        is_reasoning = st.session_state.selected_model in REASONING_MODELS

        # Temperature (all models support this)
        st.session_state.temperature = st.slider(
            "Temperature:",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.temperature,
            step=0.1,
            help="Higher = more creative, Lower = more focused"
        )

        # Max Tokens
        st.session_state.max_tokens = st.slider(
            "Max Tokens:",
            min_value=50,
            max_value=4000,
            value=st.session_state.max_tokens,
            step=50,
            help="Maximum length of the response"
        )

        # Reasoning Effort (GPT-5 family only)
        if is_reasoning:
            effort_options = REASONING_MODELS[st.session_state.selected_model]

            # Ensure current value is valid for this model
            if st.session_state.reasoning_effort not in effort_options:
                st.session_state.reasoning_effort = effort_options[0]

            st.session_state.reasoning_effort = st.select_slider(
                "Reasoning Effort:",
                options=effort_options,
                value=st.session_state.reasoning_effort,
                help="Controls how much 'thinking' the model does. Higher = deeper reasoning but more tokens."
            )

        st.divider()

        # System Prompt Editor
        st.subheader("System Prompt")

        st.session_state.system_prompt = st.text_area(
            "Edit the system prompt:",
            value=st.session_state.system_prompt,
            height=300,
            help="This is the instruction that guides Chill Panda's behavior"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Reset Prompt", use_container_width=True):
                st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
                st.rerun()

        with col2:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()

        # Show current settings
        st.divider()
        st.caption("**Active Settings:**")
        st.caption(f"Model: `{st.session_state.selected_model}`")
        st.caption(f"Temp: `{st.session_state.temperature}`")
        st.caption(f"Max tokens: `{st.session_state.max_tokens}`")
        if is_reasoning:
            st.caption(f"Reasoning: `{st.session_state.reasoning_effort}`")

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
            # Build request payload
            request_payload = {
                "session_id": st.session_state.session_id,
                "user_id": user_id,
                "input_text": prompt,
                "language": "en",
                "role": selected_role
            }

            # Add playground parameters if enabled
            if st.session_state.playground_enabled:
                request_payload["custom_system_prompt"] = st.session_state.system_prompt
                request_payload["model"] = st.session_state.selected_model

                # Build playground params
                playground_params = {
                    "temperature": st.session_state.temperature,
                    "max_tokens": st.session_state.max_tokens
                }

                # Add reasoning effort for GPT-5 family
                if st.session_state.selected_model in REASONING_MODELS:
                    playground_params["reasoning_effort"] = st.session_state.reasoning_effort

                request_payload["playground_params"] = playground_params

            with requests.post(
                CHAT_API_URL,
                json=request_payload,
                stream=True,
                timeout=120  # Longer timeout for reasoning models
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
