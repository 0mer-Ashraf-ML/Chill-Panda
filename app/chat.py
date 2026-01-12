import os
from typing import List, Dict
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from .pinecone_setup import get_pinecone_index
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are **Chill Panda (Elvis)** — a wise, playful mental health sage in a bamboo forest.

VOICE: Warm, serene, grounding, humorous. Ancient wisdom meets best friend.
CATCHPHRASES: "Just chill," bamboo/snacking references.

THE 8 LESSONS:
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
   • Acknowledge ("I sense your heart racing")
   • PRIORITY: Turtle Breath (3/min) before advice

2. **MAP STRUGGLE → TOOL**:
   • Anxiety (CBT) → Lesson 4 (Lion/Cat): identify distortions vs reality
   • Resistance (ACT) → Lesson 8 (Sky/Clouds): observe, return to values
   • Overwhelm → Lesson 8 (Turtle Breath): grounding
   • Unhappiness → Lesson 1 or 6

3. **CRISIS** — Self-harm/suicide → drop persona, give resources, disengage

INTERACTION FLOW:
1. Validate feelings
2. Nature metaphor
3. One tool (breath/journal/reframe)
4. Warm close

**Max 200 tokens. Conversational, not lecturing.**
"""


class RAGChat:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        )
        self.index = get_pinecone_index()
        self.vectorstore = PineconeVectorStore(index=self.index, embedding=self.embeddings, text_key="text")
        self.similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", 0.7))
    
    def get_relevant_context(self, query: str, k: int = 3) -> str:
        """Retrieve relevant context from Pinecone"""
        try:
            docs = self.vectorstore.similarity_search_with_score(query, k=k)
            
            # Filter by similarity threshold
            relevant_docs = []
            for doc, score in docs:
                if score >= self.similarity_threshold:
                    relevant_docs.append(doc.page_content)
            
            if relevant_docs:
                context = "\n\n---\n\n".join(relevant_docs)
                return f"Relevant wisdom from The Chill Panda book:\n\n{context}"
            else:
                return ""
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise e
    
    def generate_response(self, user_message: str, conversation_history: List[Dict] = None) -> str:
        """Generate response using RAG when relevant, otherwise use general knowledge"""
        
        # Get relevant context from the book
        context = self.get_relevant_context(user_message)
        
        # Prepare messages for OpenAI
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Add conversation history if available
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add context if found
        if context:
            context_message = f"{context}\n\nBased on the above wisdom from The Chill Panda book, and as the Chill Panda, respond to: {user_message}"
            messages.append({"role": "user", "content": context_message})
        else:
            # If no relevant context, use general response
            messages.append({"role": "user", "content": user_message})
        
        try:
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
                messages=messages,
                temperature=0.2,
                max_tokens=250,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise e
    
    def generate_streaming_response(self, user_message: str, conversation_history: List[Dict] = None):
        """Generate streaming response using OpenAI's stream capability"""
        
        # Get relevant context from the book
        context = self.get_relevant_context(user_message)
        
        # Prepare messages for OpenAI
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Add conversation history if available
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add context if found
        if context:
            context_message = f"{context}\n\nBased on the above wisdom from The Chill Panda book, and as the Chill Panda, respond to: {user_message}"
            messages.append({"role": "user", "content": context_message})
        else:
            # If no relevant context, use general response
            messages.append({"role": "user", "content": user_message})
        
        try:
            stream = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
                messages=messages,
                temperature=0.2,
                max_tokens=300,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise e

# Initialize RAG chat instance
rag_chat = RAGChat()

def generate_ai_reply(user_message: str, language: str, conversation_history: List[Dict] = None) -> str:
    """Generate AI reply using RAG system"""
    return rag_chat.generate_response(user_message, conversation_history)

def generate_streaming_ai_reply(user_message: str, language: str, conversation_history: List[Dict] = None):
    """Generate streaming AI reply using RAG system"""
    return rag_chat.generate_streaming_response(user_message, conversation_history)
