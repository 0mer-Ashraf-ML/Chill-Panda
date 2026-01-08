from .chat import generate_ai_reply
from .mongodb_manager import mongodb_manager

async def get_stress_recommendations(user_id: str, context: str):
    """
    Fetch stress reduction recommendations for a user.
    1. Attempt PDF RAG retrieval
    2. If no content, generate AI fallback
    """
    # Attempt RAG retrieval from PDF knowledge base
    rag_results = mongodb_manager.retrieve_from_pdf_knowledge(context, top_k=3)
    
    if rag_results:
        return [r["text"] for r in rag_results]

    # If RAG fails, generate AI recommendation
    prompt = (
        f"You are a wellness assistant. The user is stressed. "
        f"Detected context: {context}. "
        f"Provide 3 personalized meditation or relaxation recommendations in bullet points."
    )
    ai_reply = generate_ai_reply(user_message=prompt, language="en", conversation_history=[])
    
    # Split AI response into bullet points
    return [line.strip("-• ") for line in ai_reply.splitlines() if line.strip()]
