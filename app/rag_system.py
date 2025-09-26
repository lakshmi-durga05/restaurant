import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
import os
from typing import List, Dict, Tuple
import json

class RestaurantRAGSystem:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.llm = Ollama(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama2")
        )
        self.index = None
        self.faq_data = []
        self._initialize_faq_knowledge_base()
    
    def _initialize_faq_knowledge_base(self):
        """Initialize the FAQ knowledge base with restaurant information"""
        self.faq_data = [
            {
                "question": "What are your opening hours?",
                "answer": "We're open daily from 11:00 AM to 11:00 PM. Our kitchen closes at 10:30 PM for dinner service.",
                "category": "hours"
            },
            {
                "question": "What are your reservation policies?",
                "answer": "We accept reservations up to 3 months in advance. Cancellations must be made at least 24 hours before your reservation time. We hold tables for 15 minutes past the reservation time.",
                "category": "policies"
            },
            {
                "question": "Do you have vegetarian options?",
                "answer": "Yes! We offer a variety of vegetarian and vegan dishes. Our seasonal menu always includes several plant-based options, and our chefs are happy to accommodate special dietary requirements.",
                "category": "menu"
            },
            {
                "question": "What's your dress code?",
                "answer": "We maintain a smart casual dress code. While we don't require formal attire, we ask guests to avoid beachwear, flip-flops, and overly casual clothing.",
                "category": "policies"
            },
            {
                "question": "Do you accommodate large groups?",
                "answer": "Absolutely! We can accommodate groups of up to 12 people at our larger tables. For groups larger than 12, we can arrange multiple adjacent tables. Please call us directly for groups of 8+ people.",
                "category": "reservations"
            },
            {
                "question": "What are your special events or offers?",
                "answer": "We host wine tasting evenings every Thursday, and offer a special prix-fixe menu on Sundays. Follow us on social media for seasonal promotions and special events!",
                "category": "events"
            },
            {
                "question": "Can I bring my own wine?",
                "answer": "We have a corkage fee of $25 per bottle for wines not on our list. We kindly ask that you limit this to 2 bottles per table.",
                "category": "policies"
            },
            {
                "question": "What's your cancellation policy?",
                "answer": "We require 24 hours notice for cancellations. Late cancellations or no-shows may result in a $25 per person charge for dinner reservations.",
                "category": "policies"
            },
            {
                "question": "Do you have parking?",
                "answer": "Yes, we offer complimentary valet parking. There's also street parking available in the surrounding area.",
                "category": "services"
            },
            {
                "question": "What are your signature dishes?",
                "answer": "Our signature dishes include the Lake View Lobster Risotto, Garden Herb-Crusted Rack of Lamb, and our famous Chocolate Lava Cake. We also feature seasonal specialties that change monthly.",
                "category": "menu"
            }
        ]
        
        self._build_faiss_index()
    
    def _build_faiss_index(self):
        """Build FAISS index from FAQ data"""
        questions = [item["question"] for item in self.faq_data]
        embeddings = self.embedder.encode(questions)
        
        # Normalize embeddings
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        # Create FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        self.index.add(embeddings.astype('float32'))
    
    def find_relevant_faqs(self, query: str, top_k: int = 3) -> List[Dict]:
        """Find most relevant FAQs for a given query"""
        query_embedding = self.embedder.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # Search the index
        similarities, indices = self.index.search(
            query_embedding.astype('float32'), top_k
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.faq_data):
                results.append({
                    **self.faq_data[idx],
                    "similarity_score": float(similarities[0][i])
                })
        
        return results
    
    def generate_answer(self, query: str, relevant_faqs: List[Dict]) -> Tuple[str, float]:
        """Generate a natural answer using the LLM and relevant FAQs"""
        if not relevant_faqs:
            return "I'm sorry, I don't have specific information about that. Please feel free to call us directly for assistance.", 0.0
        
        # Use the most relevant FAQ as context
        best_faq = relevant_faqs[0]
        confidence = best_faq["similarity_score"]
        
        # If confidence is high enough, return the FAQ answer directly
        if confidence > 0.7:
            return best_faq["answer"], confidence
        
        # Otherwise, use LLM to generate a more natural response
        context = f"Based on this information: {best_faq['answer']}"
        
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a friendly restaurant host. Answer the customer's question naturally and warmly, using this information: {context}

Question: {question}

Please respond as if you're speaking directly to the customer, being helpful and welcoming:"""
        )
        
        prompt = prompt_template.format(context=context, question=query)
        
        try:
            response = self.llm(prompt)
            return response.strip(), confidence
        except Exception as e:
            # Fallback to FAQ answer if LLM fails
            return best_faq["answer"], confidence
    
    def answer_question(self, query: str) -> Tuple[str, float]:
        """Main method to answer a customer question"""
        relevant_faqs = self.find_relevant_faqs(query)
        answer, confidence = self.generate_answer(query, relevant_faqs)
        return answer, confidence
