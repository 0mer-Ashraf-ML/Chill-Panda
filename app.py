import streamlit as st
import requests
from PIL import Image
import io
from datetime import datetime

# -------------------------------
# Config
# -------------------------------
VISION_API_URL = "http://localhost:8000/vision/analyze"
BIOMETRIC_API_URL = "http://localhost:8000/biometric/ingest"

st.set_page_config(page_title="Chill Panda Demo", page_icon="🐼", layout="centered")

st.title("🐼 Chill Panda – Phase 2 Demo")

# ============================================================
# SECTION 1: FACIAL EMOTION DETECTION (VISION)
# ============================================================

st.header("📷 Facial Emotion Detection")

st.markdown(
    """
Upload a face image and get an **emotional stress analysis** from the Chill Panda backend.
"""
)

user_id = st.text_input("User ID", "test_user")

uploaded_file = st.file_uploader(
    "Upload an image (JPEG/PNG)",
    type=["jpg", "jpeg", "png"],
    key="vision_upload"
)

if uploaded_file and user_id:
    st.image(uploaded_file, caption="Uploaded Image", width=600)

    if st.button("Analyze Emotion"):
        with st.spinner("Analyzing facial emotion..."):
            try:
                image_bytes = uploaded_file.read()

                response = requests.post(
                    VISION_API_URL,
                    params={"user_id": user_id},
                    files={"image": ("image.jpg", image_bytes, uploaded_file.type)},
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    st.success("✅ Analysis complete!")

                    st.subheader("Result")
                    st.write(f"**Stress Level:** {data.get('stress_level')}")
                    st.write(f"**Emotional State:** {data.get('emotional_state')}")
                    st.write(f"**Confidence:** {data.get('confidence'):.2f}")
                    st.write(f"**Source:** {data.get('source')}")
                    st.write(f"**Timestamp:** {data.get('created_at')}")
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")

            except Exception as e:
                st.error(f"Exception: {e}")

# ============================================================
# SECTION 2: BIOMETRIC INTEGRATION (PHASE 2)
# ============================================================

st.divider()
st.header("❤️ Biometric Stress Monitoring")

st.markdown(
    """
Simulate **near real-time biometric data** from wearables  
(Apple Health / Google Fit / Any wearable via abstraction).
"""
)

# -------------------------------
# Simulated Biometric Inputs
# -------------------------------
col1, col2 = st.columns(2)

with col1:
    heart_rate = st.slider(
        "Heart Rate (BPM)",
        min_value=40,
        max_value=160,
        value=72
    )

with col2:
    hrv = st.slider(
        "Heart Rate Variability (ms)",
        min_value=5,
        max_value=100,
        value=35
    )

timestamp = datetime.utcnow().isoformat()

# -------------------------------
# Submit Biometric Data
# -------------------------------
if st.button("Send Biometric Data"):
    with st.spinner("Sending biometric data..."):
        try:
            response = requests.post(
                BIOMETRIC_API_URL,
                data={
                    "user_id": user_id,
                    "heart_rate": heart_rate,
                    "hrv": hrv
                },
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()["data"]
                st.success("✅ Biometric data ingested successfully!")

                st.subheader("Biometric Result")
                st.write(f"**Heart Rate:** {data.get('heart_rate')} bpm")
                st.write(f"**HRV:** {data.get('hrv')} ms")
                st.write(f"**Stress Event Detected:** {data.get('stress_event')}")
                st.write(f"**Timestamp:** {data.get('timestamp')}")

                if data.get("stress_event"):
                    st.warning("⚠️ Stress spike detected! Wellness intervention triggered.")
                else:
                    st.info("🧘 Biometrics look normal. No intervention needed.")

            else:
                st.error(f"Error: {response.status_code} - {response.text}")

        except Exception as e:
            st.error(f"Exception: {e}")
