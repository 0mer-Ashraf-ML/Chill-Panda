import os
import PyPDF2
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone_setup import get_pinecone_index
from dotenv import load_dotenv

load_dotenv()

class DocumentProcessor:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        )
        self.index = get_pinecone_index()
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
        return text
    
    def chunk_document(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Split document into chunks"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        return text_splitter.split_text(text)
    
    def embed_and_store(self, chunks: List[str], metadata: List[Dict[str, Any]] = None):
        """Embed chunks and store in Pinecone"""
        if metadata is None:
            metadata = [{"source": "chill-panda-book", "chunk_id": i} for i in range(len(chunks))]
        
        # Create vector store
        vectorstore = PineconeVectorStore.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            metadatas=metadata,
            index_name=os.getenv("PINECONE_INDEX_NAME")
        )
        
        return vectorstore
    
    def process_pdf(self, pdf_path: str):
        """Process PDF and store in Pinecone"""
        text = self.extract_text_from_pdf(pdf_path)
        chunks = self.chunk_document(text)
        self.embed_and_store(chunks)

# Run this once to process the PDF
if __name__ == "__main__":
    processor = DocumentProcessor()
    processor.process_pdf("./data/The Chill Panda B+.pdf")