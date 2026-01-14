import os
from typing import List, Dict
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from .pinecone_setup import get_pinecone_index
from .prompt_generator import generate_system_prompt
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class RAGChat:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
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
        conversation_history: List[Dict] = None
    ):
        # Generate full system prompt with role + base
        system_prompt = generate_system_prompt(role)

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
        conversation_history: List[Dict] = None
    ) -> str:
        messages = self._build_messages(user_message, role, conversation_history)

        print("----- Message -----")
        print(messages)
        print("----- END -----")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
            messages=messages,
            temperature=0.2,
            max_tokens=250
        )

        return response.choices[0].message.content.strip()

    def generate_streaming_response(
        self,
        user_message: str,
        role: str,
        conversation_history: List[Dict] = None
    ):
        messages = self._build_messages(user_message, role, conversation_history)

        print("----- Message -----")
        print(messages)
        print("----- END -----")

        stream = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
            messages=messages,
            temperature=0.2,
            max_tokens=300,
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Singleton
rag_chat = RAGChat()


def generate_ai_reply(user_message, role, conversation_history=None):
    return rag_chat.generate_response(user_message, role, conversation_history)


def generate_streaming_ai_reply(user_message, role, conversation_history=None):
    return rag_chat.generate_streaming_response(user_message, role, conversation_history)
