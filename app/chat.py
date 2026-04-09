import os
from typing import List, Dict, Optional, Any
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from .pinecone_setup import get_pinecone_index
from .prompt_generator import generate_system_prompt
from .model_config import build_api_params, DEFAULT_MODEL, is_reasoning_model
from .llm_provider import create_sync_llm_client, get_embedding_client_kwargs
from dotenv import load_dotenv

load_dotenv()

client = create_sync_llm_client()


class RAGChat:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
            **get_embedding_client_kwargs()
        )
        self.index = get_pinecone_index()
        self.vectorstore = PineconeVectorStore(
            index=self.index,
            embedding=self.embeddings,
            text_key="text"
        )
        self.similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", 0.7))

    def get_relevant_context(self, query: str, k: int = 3) -> str:
        try:
            docs = self.vectorstore.similarity_search_with_score(query, k=k)
            relevant_docs = [
                doc.page_content for doc, score in docs
                if score >= self.similarity_threshold
            ]

            if relevant_docs:
                return (
                    "Relevant wisdom from The Chill Panda book:\n\n"
                    + "\n\n---\n\n".join(relevant_docs)
                )
            return ""
        except Exception as e:
            raise e

    def _build_messages(
        self,
        user_message: str,
        role: str,
        conversation_history: List[Dict] = None,
        custom_system_prompt: Optional[str] = None,
        language: str = "en"
    ):
        # Use custom prompt if provided, otherwise generate the default
        if custom_system_prompt is not None:
            system_prompt = custom_system_prompt
        else:
            system_prompt = generate_system_prompt(role, language)

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        context = self.get_relevant_context(user_message)
        if context:
            messages.append({
                "role": "user",
                "content": f"{context}\n\nRespond as Chill Panda:\n{user_message}"
            })
        else:
            messages.append({"role": "user", "content": user_message})

        return messages

    def generate_response(
        self,
        user_message: str,
        role: str,
        conversation_history: List[Dict] = None,
        custom_system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        playground_params: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> str:
        messages = self._build_messages(
            user_message, role, conversation_history, custom_system_prompt, language
        )

        print("----- Message -----")
        print(messages)
        print("----- END -----")

        # Determine model to use
        selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

        # Build parameters with defaults, allowing playground overrides
        params = playground_params or {}
        api_params = build_api_params(
            model_id=selected_model,
            messages=messages,
            temperature=params.get("temperature", 0.7),
            max_tokens=params.get("max_tokens", 200),
            presence_penalty=params.get("presence_penalty", 0.3),
            frequency_penalty=params.get("frequency_penalty", 0.3),
            reasoning_effort=params.get("reasoning_effort"),
            stream=False
        )

        response = client.chat.completions.create(**api_params)

        return response.choices[0].message.content.strip()

    def generate_streaming_response(
        self,
        user_message: str,
        role: str,
        conversation_history: List[Dict] = None,
        custom_system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        playground_params: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ):
        messages = self._build_messages(
            user_message, role, conversation_history, custom_system_prompt, language
        )

        print("----- Message -----")
        print(messages)
        print("----- END -----")

        # Determine model to use
        selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

        # Build parameters with defaults, allowing playground overrides
        params = playground_params or {}
        api_params = build_api_params(
            model_id=selected_model,
            messages=messages,
            temperature=params.get("temperature", 0.2),
            max_tokens=params.get("max_tokens", 300),
            presence_penalty=params.get("presence_penalty"),
            frequency_penalty=params.get("frequency_penalty"),
            reasoning_effort=params.get("reasoning_effort"),
            stream=True
        )

        stream = client.chat.completions.create(**api_params)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


_rag_chat: Optional[RAGChat] = None


def get_rag_chat() -> RAGChat:
    global _rag_chat
    if _rag_chat is None:
        _rag_chat = RAGChat()
    return _rag_chat


def generate_ai_reply(
    user_message,
    role,
    conversation_history=None,
    custom_system_prompt=None,
    model=None,
    playground_params=None,
    language="en"
):
    return get_rag_chat().generate_response(
        user_message,
        role,
        conversation_history,
        custom_system_prompt,
        model,
        playground_params,
        language
    )


def generate_streaming_ai_reply(
    user_message,
    role,
    conversation_history=None,
    custom_system_prompt=None,
    model=None,
    playground_params=None,
    language="en"
):
    return get_rag_chat().generate_streaming_response(
        user_message,
        role,
        conversation_history,
        custom_system_prompt,
        model,
        playground_params,
        language
    )
