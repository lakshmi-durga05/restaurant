from typing import List, Dict, Any, Optional
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
import json

class AIService:
    def __init__(self, model_name: str = "llama2"):
        """Initialize the AI service with a local LLM via Ollama"""
        self.llm = Ollama(model=model_name, temperature=0.7)
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self.setup_chains()
    
    def setup_chains(self):
        """Set up the conversation chain with system prompt"""
        system_prompt = """You are an AI assistant for a restaurant booking system. Help users with:
        - Making reservations
        - Answering questions about the restaurant
        - Providing menu information
        - Handling special requests
        
        Be friendly, helpful, and concise in your responses."""
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])
        
        self.conversation_chain = self.prompt | self.llm | StrOutputParser()
    
    async def process_message(self, user_input: str, session_id: str = "default") -> str:
        """Process a user message and return the AI response"""
        # Add user message to memory
        self.memory.save_context({"input": user_input}, {"output": ""})
        
        # Get chat history
        chat_history = self.memory.load_memory_variables({})["chat_history"]
        
        # Generate response
        response = await self.conversation_chain.ainvoke({
            "input": user_input,
            "chat_history": chat_history
        })
        
        # Add AI response to memory
        self.memory.save_context({"input": user_input}, {"output": response})
        
        return response
    
    def extract_booking_info(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract structured booking information from user input"""
        prompt = f"""Extract the following information from the user's message in JSON format:
        - name (string)
        - party_size (integer)
        - date (YYYY-MM-DD or relative like 'tomorrow')
        - time (HH:MM in 24h format)
        - special_requests (string, optional)
        
        User input: {user_input}
        
        Return only the JSON object, nothing else."""
        
        try:
            response = self.llm.invoke(prompt)
            # Clean the response to get valid JSON
            json_str = response.strip().replace('```json', '').replace('```', '').strip()
            return json.loads(json_str)
        except Exception as e:
            print(f"Error extracting booking info: {e}")
            return None
