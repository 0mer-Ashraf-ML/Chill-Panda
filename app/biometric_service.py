# app/biometric_service.py
from .recommendation_service import get_stress_recommendations

STRESS_HR_THRESHOLD = 100
STRESS_HRV_THRESHOLD = 20

async def detect_stress(data: dict):
    hr = data.get("heart_rate")
    hrv = data.get("hrv")
    user_id = data.get("user_id", "unknown")

    stressed = hr > STRESS_HR_THRESHOLD or hrv < STRESS_HRV_THRESHOLD
    recommendations = []

    if stressed:
        context = f"Heart Rate: {hr}, HRV: {hrv}"
        recommendations = await get_stress_recommendations(user_id, context)

    return stressed, recommendations
