import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

# API Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')

# Database Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'chillpanda_db')

# Pinecone Configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'chill-panda')

# App Configuration
ENV = os.getenv('ENV', 'development')
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
MAX_HISTORY_MESSAGES = int(os.getenv('MAX_HISTORY_MESSAGES', '50'))

# CORS Configuration
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:8501').split(',')

# RAG Configuration
RAG_SIMILARITY_THRESHOLD = float(os.getenv('RAG_SIMILARITY_THRESHOLD', '0.7'))
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Voice Usage Limits Configuration (in minutes)
VOICE_LIMIT_SESSION_MINUTES = int(os.getenv('VOICE_LIMIT_SESSION_MINUTES', '1'))  # 10 minutes per session
VOICE_LIMIT_DAILY_MINUTES = int(os.getenv('VOICE_LIMIT_DAILY_MINUTES', '3'))      # 50 minutes per day
VOICE_LIMIT_MONTHLY_MINUTES = int(os.getenv('VOICE_LIMIT_MONTHLY_MINUTES', '5')) # 200 minutes per month

# Voice Usage Tracking Configuration
VOICE_USAGE_ENABLED = os.getenv('VOICE_USAGE_ENABLED', 'true').lower() == 'true'
VOICE_ABUSE_DETECTION_ENABLED = os.getenv('VOICE_ABUSE_DETECTION_ENABLED', 'true').lower() == 'true'

# Abuse Detection Thresholds
VOICE_ABUSE_CONTINUOUS_THRESHOLD_MINUTES = int(os.getenv('VOICE_ABUSE_CONTINUOUS_THRESHOLD_MINUTES', '30'))  # Flag if continuous use > 30 mins
VOICE_ABUSE_RECONNECT_THRESHOLD = int(os.getenv('VOICE_ABUSE_RECONNECT_THRESHOLD', '10'))  # Flag if > 10 reconnects in 5 mins
VOICE_ABUSE_RECONNECT_WINDOW_SECONDS = int(os.getenv('VOICE_ABUSE_RECONNECT_WINDOW_SECONDS', '300'))  # 5 minute window

# Audio Configuration (for duration calculation)
AUDIO_SAMPLE_RATE = 16000  # 16kHz
AUDIO_BITS_PER_SAMPLE = 16  # 16-bit
AUDIO_CHANNELS = 1  # Mono
# Bytes per millisecond = (sample_rate * channels * bits_per_sample / 8) / 1000
AUDIO_BYTES_PER_MS = (AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * AUDIO_BITS_PER_SAMPLE // 8) // 1000  # = 32