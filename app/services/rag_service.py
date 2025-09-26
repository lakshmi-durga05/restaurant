from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import os
import json

class RAGService:
    def __init__(self, knowledge_base_dir: str = "data/knowledge_base"):
        """Initialize the RAG service with knowledge base"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.knowledge_base_dir = knowledge_base_dir
        self.vector_store = None
        self.setup_knowledge_base()
    
    def setup_knowledge_base(self):
        """Load or create the vector store from documents"""
        if os.path.exists("data/vector_store"):
            self.vector_store = FAISS.load_local("data/vector_store", self.embeddings)
        else:
            self.ingest_documents()
    
    def ingest_documents(self):
        """Process and embed documents from the knowledge base"""
        if not os.path.exists(self.knowledge_base_dir):
            os.makedirs(self.knowledge_base_dir, exist_ok=True)
            self._create_sample_knowledge()
        
        documents = []
        for filename in os.listdir(self.knowledge_base_dir):
            if filename.endswith('.json'):
                with open(os.path.join(self.knowledge_base_dir, filename), 'r') as f:
                    data = json.load(f)
                    content = f"{data.get('title', '')}\n\n{data.get('content', '')}"
                    metadata = {
                        "source": filename,
                        "title": data.get('title', 'Untitled')
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
        
        if documents:
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            splits = text_splitter.split_documents(documents)
            
            # Create and save the vector store
            self.vector_store = FAISS.from_documents(splits, self.embeddings)
            os.makedirs("data/vector_store", exist_ok=True)
            self.vector_store.save_local("data/vector_store")
    
    def query(self, question: str, k: int = 3) -> List[Dict[str, Any]]:
        """Query the knowledge base for relevant information"""
        if not self.vector_store:
            return [{"content": "Knowledge base not available.", "source": ""}]
        
        docs = self.vector_store.similarity_search(question, k=k)
        return [{
            "content": doc.page_content,
            "source": doc.metadata.get("source", "unknown"),
            "title": doc.metadata.get("title", "Untitled")
        } for doc in docs]
    
    def _create_sample_knowledge(self):
        """Create sample knowledge base if none exists"""
        sample_data = [
            {
                "title": "Restaurant Hours",
                "content": "We are open from 11:00 AM to 10:00 PM from Monday to Saturday, "
                          "and from 12:00 PM to 9:00 PM on Sundays. We are closed on major holidays."
            },
            {
                "title": "Reservation Policy",
                "content": "Reservations can be made up to 30 days in advance. We hold tables for "
                          "15 minutes past the reservation time. For groups larger than 6, please "
                          "call us directly at (555) 123-4567."
            },
            {
                "title": "Menu Highlights",
                "content": "Our menu features locally-sourced ingredients with both vegetarian and "
                          "non-vegetarian options. Must-try dishes include our signature steak, "
                          "truffle pasta, and chocolate lava cake. We also offer a selection of "
                          "fine wines and craft cocktails."
            }
        ]
        
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        for i, data in enumerate(sample_data):
            with open(os.path.join(self.knowledge_base_dir, f"doc_{i+1}.json"), 'w') as f:
                json.dump(data, f, indent=2)
