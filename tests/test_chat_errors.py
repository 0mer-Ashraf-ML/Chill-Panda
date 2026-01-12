import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.chat import RAGChat

class TestChatErrors(unittest.TestCase):
    @patch('app.chat.OpenAIEmbeddings')
    @patch('app.chat.get_pinecone_index')
    @patch('app.chat.PineconeVectorStore')
    def setUp(self, mock_pvs, mock_gpi, mock_oe):
        # Create a mock for the vectorstore instance
        self.mock_vectorstore = MagicMock()
        mock_pvs.return_value = self.mock_vectorstore
        self.chat = RAGChat()

    def test_get_relevant_context_error(self):
        self.mock_vectorstore.similarity_search_with_score.side_effect = Exception("Pinecone Error")
        with self.assertRaises(Exception) as cm:
            self.chat.get_relevant_context("hello")
        self.assertEqual(str(cm.exception), "Pinecone Error")

    @patch('app.chat.client.chat.completions.create')
    def test_generate_response_error(self, mock_create):
        # Mock get_relevant_context to avoid calling mock_vectorstore
        with patch.object(RAGChat, 'get_relevant_context', return_value=""):
            mock_create.side_effect = Exception("OpenAI Error")
            with self.assertRaises(Exception) as cm:
                self.chat.generate_response("hello")
            self.assertEqual(str(cm.exception), "OpenAI Error")

    @patch('app.chat.client.chat.completions.create')
    def test_generate_streaming_response_error(self, mock_create):
        # Mock get_relevant_context to avoid calling mock_vectorstore
        with patch.object(RAGChat, 'get_relevant_context', return_value=""):
            mock_create.side_effect = Exception("OpenAI Streaming Error")
            
            gen = self.chat.generate_streaming_response("hello")
            with self.assertRaises(Exception) as cm:
                next(gen)
            self.assertEqual(str(cm.exception), "OpenAI Streaming Error")

if __name__ == '__main__':
    unittest.main()
