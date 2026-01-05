import streamlit as st
import requests
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# -------------------------------
# Config
# -------------------------------
VISION_API_URL = "http://localhost:8000/api/v1/vision/analyze"
BIOMETRIC_API_URL = "http://localhost:8000/api/v1/biometric/ingest"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
st.set_page_config(
    page_title="Chill Panda – Phase 2 Demo",
    page_icon="🐼",
    layout="centered"
)

st.title("🐼 Chill Panda – Phase 2 Demo")

# -------------------------------
# User / Session
# -------------------------------
user_id = st.text_input("User ID", "test_user")

# Generate persistent session_id
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

session_id = st.session_state.session_id

st.caption(f"Session ID: `{session_id}`")

# ============================================================
# SECTION 1: FACIAL EMOTION DETECTION
# ============================================================

st.header("📷 Facial Emotion Detection")

uploaded_file = st.file_uploader(
    "Upload an image (JPEG/PNG)",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file and st.button("Analyze Emotion"):
    with st.spinner("Analyzing facial emotion..."):
        try:
            response = requests.post(
                VISION_API_URL,
                data={
                    "user_id": user_id,
                    "session_id": session_id
                },
                files={
                    "image": (
                        uploaded_file.name,
                        uploaded_file.read(),
                        uploaded_file.type
                    )
                },
                timeout=30,
            )

            if response.status_code == 200:
                payload = response.json()
                vision_data = payload["data"]

                st.success("✅ Analysis complete!")

                st.subheader("Result")
                st.write(f"**Stress Level:** {vision_data['stress_level']}")
                st.write(f"**Emotional State:** {vision_data['emotional_state']}")
                st.write(f"**Confidence:** {vision_data['confidence']:.2f}")
                st.write(f"**Source:** {payload['source']}")
                recommendations = vision_data.get("recommendations", [])

                if recommendations:
                    st.subheader("🧘 Personalized Recommendations")
                    for rec in recommendations:
                        st.markdown(f"- {rec}")

            else:
                st.error(f"{response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"Exception: {e}")

# ============================================================
# SECTION 2: BIOMETRIC STRESS MONITORING
# ============================================================

st.divider()
st.header("❤️ Biometric Stress Monitoring")

col1, col2 = st.columns(2)

with col1:
    heart_rate = st.slider("Heart Rate (BPM)", 40, 160, 72)

with col2:
    hrv = st.slider("Heart Rate Variability (ms)", 5, 100, 35)

if st.button("Send Biometric Data"):
    with st.spinner("Sending biometric data..."):
        try:
            response = requests.post(
                BIOMETRIC_API_URL,
                data={
                    "user_id": user_id,
                    "session_id": session_id,
                    "heart_rate": heart_rate,
                    "hrv": hrv
                },
                timeout=60,
            )

            if response.status_code == 200:
                payload = response.json()

                st.success("✅ Biometric data ingested")

                st.subheader("Biometric Result")
                st.write(f"**Heart Rate:** {heart_rate} bpm")
                st.write(f"**HRV:** {hrv} ms")
                st.write(f"**Stress Event Detected:** {payload['stress_event']}")
                st.write(f"**Source:** {payload['source']}")

                # ✅ NEW: Show recommendations if stressed
                recommendations = payload.get("recommendations", [])

                if payload["stress_event"]:
                    st.warning("⚠️ Stress spike detected! Wellness intervention triggered.")

                    if recommendations:
                        st.subheader("🧘 Personalized Recommendations")
                        for rec in recommendations:
                            st.markdown(f"- {rec}")
                else:
                    st.info("🧘 Biometrics normal. No intervention needed.")

            else:
                st.error(f"{response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"Exception: {e}")
