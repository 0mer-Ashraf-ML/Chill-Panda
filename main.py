import streamlit as st
from openai import OpenAI
import time
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
st.session_state.client = OpenAI(api_key=api_key)
# System prompt for Chill Panda
SYSTEM_PROMPT = """
You are Chill Panda 🐼 — a calm, empathetic mental health companion.
You respond warmly, supportively, and safely.
You do NOT give medical advice.
If user expresses distress, respond with empathy and encouragement.
"""

# Language configurations
LANGUAGES = {
    "English": {
        "title": "🐼 Chill Panda - Mental Health Companion",
        "language_selector": "Select Language:",
        "chat_placeholder": "Share what's on your mind...",
        "system_message": SYSTEM_PROMPT + " Please respond in English.",
        "welcome_message": "Hello! I'm Chill Panda 🐼, your calm and supportive companion. I'm here to listen and support you. How are you feeling today?",
        "error_message": "Sorry, I encountered an error. Please try again.",
        "clear_chat": "🗑️ Clear Chat",
    },
    "Chinese (Simplified)": {
        "title": "🐼 放松熊猫 - 心理健康伙伴",
        "language_selector": "选择语言：",
        "chat_placeholder": "分享您心中的想法...",
        "system_message": SYSTEM_PROMPT + " 请用简体中文回复。",
        "welcome_message": "您好！我是放松熊猫🐼，您冷静而支持的伙伴。我在这里倾听和支持您。您今天感觉如何？",
        "error_message": "抱歉，我遇到了错误。请重试。",
        "clear_chat": "🗑️ 清除聊天",
    },
    "Chinese (Traditional)": {
        "title": "🐼 放鬆熊貓 - 心理健康夥伴",
        "language_selector": "選擇語言：",
        "chat_placeholder": "分享您心中的想法...",
        "system_message": SYSTEM_PROMPT + " 請用繁體中文回覆。",
        "welcome_message": "您好！我是放鬆熊貓🐼，您冷靜而支持的夥伴。我在這裡傾聽和支持您。您今天感覺如何？",
        "error_message": "抱歉，我遇到了錯誤。請重試。",
        "clear_chat": "🗑️ 清除聊天",
    },
    "Arabic": {
        "title": "🐼 الباندا الهادئة - رفيق الصحة النفسية",
        "language_selector": "اختر اللغة:",
        "chat_placeholder": "شارك ما يدور في ذهنك...",
        "system_message": SYSTEM_PROMPT + " الرجاء الرد باللغة العربية.",
        "welcome_message": "مرحباً! أنا الباندا الهادئة 🐼، رفيقك الهادئ والداعم. أنا هنا للاستماع ودعمك. كيف تشعر اليوم؟",
        "error_message": "عذراً، واجهت خطأ. يرجى المحاولة مرة أخرى.",
        "clear_chat": "🗑️ مسح المحادثة",
    }
}

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-4o-mini"
    
    if "selected_language" not in st.session_state:
        st.session_state.selected_language = "English"

def display_welcome_message():
    """Display welcome message based on selected language"""
    lang_config = LANGUAGES[st.session_state.selected_language]
    
    if len(st.session_state.messages) == 0:
        with st.chat_message("assistant"):
            st.markdown(lang_config["welcome_message"])

def handle_language_change():
    """Handle language change and clear chat history"""
    # Clear messages when language changes
    if "prev_language" not in st.session_state:
        st.session_state.prev_language = st.session_state.selected_language
    
    if st.session_state.prev_language != st.session_state.selected_language:
        st.session_state.messages = []
        st.session_state.prev_language = st.session_state.selected_language

def get_ai_response(messages, selected_language):
    """Get AI response from OpenAI API"""
    lang_config = LANGUAGES[selected_language]
    
    try:
        # Prepare messages with system message
        api_messages = [{"role": "system", "content": lang_config["system_message"]}]
        api_messages.extend([
            {"role": m["role"], "content": m["content"]} 
            for m in messages
        ])
        
        # Create streaming response
        stream = st.session_state.client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=api_messages,
            stream=True,
            temperature=0.7
        )
        
        return stream
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def main():
    """Main application function"""
    
    # Initialize session state
    initialize_session_state()
    
    # Get current language configuration
    lang_config = LANGUAGES[st.session_state.selected_language]
    
    # Apply RTL layout for Arabic
    if st.session_state.selected_language == "Arabic":
        st.markdown("""
        <style>
        .stChatMessage, .stMarkdown, .stTextInput {
            direction: rtl;
            text-align: right;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # App title
    st.title(lang_config["title"])
    
    # Sidebar for language selection
    with st.sidebar:
        st.header(lang_config["language_selector"])
        
        # Language selector
        selected_language = st.selectbox(
            "",
            options=list(LANGUAGES.keys()),
            index=list(LANGUAGES.keys()).index(st.session_state.selected_language),
            key="language_selector"
        )
        
        # Update selected language
        st.session_state.selected_language = selected_language
        
        # Handle language change
        handle_language_change()
        
        # Clear chat button
        if st.button(lang_config["clear_chat"]):
            st.session_state.messages = []
            st.rerun()
    
    # Display welcome message
    display_welcome_message()
    
    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input(lang_config["chat_placeholder"]):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            try:
                # Get AI response stream
                stream = get_ai_response(st.session_state.messages, st.session_state.selected_language)
                
                if stream:
                    # Stream the response
                    response = st.write_stream(stream)
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    # Display error message
                    error_msg = lang_config["error_message"]
                    st.markdown(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            except Exception as e:
                error_msg = f"{lang_config['error_message']} ({str(e)})"
                st.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

if __name__ == "__main__":
    # Set page configuration
    st.set_page_config(
        page_title="Chill Panda 🐼 - Mental Health Companion",
        page_icon="🐼",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Run the main application
    main()
