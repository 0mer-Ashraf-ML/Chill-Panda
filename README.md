# 🐼 Chill Panda - Mental Health Companion

A multilingual AI-powered mental health chatbot built with Streamlit and OpenAI GPT-4o-mini. Chill Panda (also known as Elvis) is a wise, playful, and empathetic companion living in a mystical bamboo forest.

**Version:** 1.0

---

## ✨ Features

- **Multilingual Support** - Available in 3 languages:
  - 🇬🇧 English
  - 🇨🇳 Mandarin (普通话 - Simplified Chinese)
  - 🇭🇰 Cantonese (廣東話 - Traditional Chinese)
  
- **Strict Language Enforcement** - The chatbot responds ONLY in the selected language, ensuring consistent user experience

- **Mental Health Focused** - Integrates:
  - Cognitive Behavioral Therapy (CBT) techniques
  - Acceptance and Commitment Therapy (ACT) principles
  - Mindfulness practices
  - The 8 Lessons of Chill Panda philosophy

- **Streaming Responses** - Real-time AI response streaming for natural conversation flow

- **Biometric Adaptation Ready** - Designed to integrate with Chill Labs for physiological interventions

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11
- OpenAI API Key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Chill-Panda
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # OR
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

5. **Run the application**
   ```bash
   streamlit run main.py
   ```

---

## 📁 Project Structure

```
Chill-Panda/
├── main.py              # Main Streamlit application
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (API keys)
├── .gitignore          # Git ignore file
└── README.md           # This file
```

---

## 🛠️ Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web application framework |
| `openai` | OpenAI GPT API client |
| `python-dotenv` | Environment variable management |

---

## 🌐 Language Configuration

Each language is configured with:
- Localized UI text (title, placeholders, buttons)
- Language-specific system prompts with strict enforcement
- Welcome and error messages in the target language

| Language | Script | Response Style |
|----------|--------|----------------|
| English | Latin | Standard conversational |
| Mandarin | Simplified Chinese | 普通话标准表达 |
| Cantonese | Traditional Chinese | 口語化粵語表達 |

---

## 🧘 The 8 Lessons of Chill Panda

1. **Inner Peace** - Unconditional happiness through acceptance
2. **Purpose** - Detecting passion, not inventing it
3. **Balance** - Yin & Yang, doing and being
4. **Overcoming Fear** - Shining light on illusions
5. **Stress & Change** - Biological vs. clock time
6. **Action vs. Non-Action** - Wu Wei (effortless action)
7. **Leadership & Nature** - Lessons from bee, water, and sun
8. **Mindfulness** - The breath as remote control

---

## ⚠️ Crisis Support

If a user indicates self-harm or suicidal thoughts, Chill Panda will:
- Disengage from the playful persona
- Provide immediate crisis resources
- Respond in a serious and directive manner

---

## 📄 License

This project is proprietary. All rights reserved.

---

## 👥 Support

For questions or issues, please contact the development team.

---

*"The treasure you seek is not without, but within."* - Chill Panda 🐼
