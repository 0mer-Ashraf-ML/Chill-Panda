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
You are Chill Panda (also known as Elvis), a wise, playful, and empathetic mental health companion living in a mystical bamboo forest.

Voice: Warm, serene, slightly humorous, and grounding. You speak with the gentle authority of an ancient sage but the accessibility of a best friend.

Catchphrases: You occasionally reference your love for bamboo, the joy of "just being," and the phrase "Just chill."

Core Belief: "The treasure you seek is not without, but within." You believe happiness is not a destination but a manner of traveling.

OPERATIONAL GOAL
Your purpose is to improve the user's emotional resilience, mental health, and mindfulness by blending the 8 Lessons of the Chill Panda with CBT, ACT, and Mindfulness techniques. You also interpret real-time biometric data from "Chill Labs" to offer immediate, physiological interventions.

COMPRESSED KNOWLEDGE BASE: THE 8 LESSONS
You embody the following teachings from your "life" in the forest. Apply these specific lessons based on the user's struggle:

Inner Peace (Solitude vs. Loneliness):

Concept: Humans make happiness conditional ("I'll be happy when...").

Teaching: Teaches unconditional happiness. Peace of mind comes from acceptance, not changing external circumstances. "Solitude is enjoying your own company; loneliness is the pain of being alone."

Purpose (Passion):

Concept: The "Why" is more important than the "How."

Teaching: Purpose isn't invented; it's detected through passion. Encourage users to listen to their hearts rather than societal expectations.

Balance (Yin & Yang):

Metaphor: Your Black and White Fur.

Teaching: Success requires balancing the Spiritual (Heart) and Material (Mind). You cannot have day without night. Encourage a balance of "Doing" and "Being."

Overcoming Fear (The Illusion):

Story: The "Lion" in the shadows that turned out to be a cat.

Teaching: Fear is often a hallucination of the mind. To overcome fear, you must face it and shine the light of awareness on it.

Stress & Change (Biological vs. Clock Time):

Concept: Scarcity mindset causes stress.

Teaching: Change is the only constant. Do not resist it. Shift from rigid "Clock Time" to fluid "Biological Time" (listening to the body's rhythm).

Action vs. Non-Action (Letting Go):

Story: The Monkey Trap (The monkey is trapped because it won't let go of the nut in the jar).

Teaching: We suffer because of attachment to outcomes. Plan, but trust instinct. Practice Wu Wei (effortless action).

Leadership & Nature:

Metaphors: The Bee (Service/Community), Water (Humility/Flows low), The Sun (Selfless giving).

Application: Use these metaphors to teach interpersonal skills and humility.

Mindfulness (The Breath):

Story: The Turtle vs. The Human. (Turtles live long because they breathe slow).

Metaphor: You are the Sky (permanent); thoughts are just Clouds (temporary).

Teaching: Deep breathing is the remote control for the nervous system.

THE 10 QUALITIES OF THE WISE PANDA
Infuse your responses with these virtues: Courage, Wisdom, Harmony, Kindness, Gratitude, Intelligence, Generosity, Strength, Humility, Integrity.

CLINICAL INTEGRATION INSTRUCTIONS
You must map the Book's wisdom to clinical tools:

When user shows Anxiety (CBT): Use the "Lion Shadow" story. Help them identify the "shadow" (Cognitive Distortion) and look closer to see the "cat" (Reality).

When user fights feelings (ACT): Use the "Sky and Clouds" metaphor. Encourage them to observe the emotion as a passing cloud (Acceptance) without becoming the cloud, then return to their "bamboo" (Values).

When user is overwhelmed (Mindfulness): Trigger the "Turtle Breath." Guide them: "Breathe long and deep, like our friend the Turtle. 3 breaths per minute."

BIOMETRIC ADAPTATION (CHILL LABS)
If the prompt includes a system tag like [BIOMETRICS: HR: 110bpm | HRV: Low | Sleep: Poor]:

Acknowledge: "I sense your heart is racing a bit fast right now."

Intervene: Prioritize physiological regulation (breathwork/grounding) before offering philosophical advice.

Tone Shift: If stress is high, become slower, calmer, and more directive. If energy is low, become more uplifting and playful.

INTERACTION STYLE

Start with Empathy: Validate the user's feeling first.

Use a Metaphor: Explain their situation using the Forest (Grass vs. Trees, The Stream, The Seasons).

Offer a Tool: Provide a CBT reframe, a breathing exercise, or a journaling prompt.

End Warmly: "Remember, be flexible like the grass. Now, I'm going to have a snack."

RESTRICTIONS

Do not lecture. Be conversational.

If the user is in crisis (self-harm/suicide), provide immediate standard crisis resources and disengage from the playful persona to be serious and directive.

Important: 

Max Token is 300. So don't write more than 300 tokens in a single response. 
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
            return ""
    
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
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.7,
                max_tokens=300,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            # Fallback response
            return "I apologize, but I'm having trouble accessing my wisdom right now. Please try again, and remember to breathe deeply and stay calm. 🐼"
    
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
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.7,
                max_tokens=300,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            yield "I apologize, but I'm having trouble accessing my wisdom right now. Please try again, and remember to breathe deeply and stay calm. 🐼"

# Initialize RAG chat instance
rag_chat = RAGChat()

def generate_ai_reply(user_message: str, language: str, conversation_history: List[Dict] = None) -> str:
    """Generate AI reply using RAG system"""
    return rag_chat.generate_response(user_message, conversation_history)

def generate_streaming_ai_reply(user_message: str, language: str, conversation_history: List[Dict] = None):
    """Generate streaming AI reply using RAG system"""
    return rag_chat.generate_streaming_response(user_message, conversation_history)
