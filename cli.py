import asyncio
import os
import sys
from typing import Optional
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import AIService
from app.services.rag_service import RAGService

class RestaurantAIChat:
    def __init__(self):
        self.ai_service = AIService()
        self.rag_service = RAGService()
        self.running = True
    
    async def start(self):
        print("\n🍽️  Welcome to the Restaurant AI Assistant!")
        print("Type 'exit' to quit at any time.\n")
        
        while self.running:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("\n👋 Thank you for using our service! Have a great day!")
                    self.running = False
                    continue
                
                # Check if this is a general question or a booking request
                if self._is_booking_request(user_input):
                    await self._handle_booking(user_input)
                else:
                    # Use RAG to get relevant information
                    context = self.rag_service.query(user_input)
                    if context:
                        context_str = "\n".join([f"[{doc['title']}] {doc['content']}" for doc in context])
                        response = await self.ai_service.process_message(
                            f"Context: {context_str}\n\nQuestion: {user_input}"
                        )
                    else:
                        response = await self.ai_service.process_message(user_input)
                    
                    print(f"\n🤖 {response}")
            
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                self.running = False
            except Exception as e:
                print(f"\n❌ An error occurred: {str(e)}")
    
    def _is_booking_request(self, text: str) -> bool:
        """Check if the user is trying to make a reservation"""
        keywords = ['book', 'reservation', 'reserve', 'table', 'dinner', 'lunch', 'booking']
        return any(keyword in text.lower() for keyword in keywords)
    
    async def _handle_booking(self, user_input: str):
        """Handle booking requests"""
        print("\n🔍 I'll help you with that reservation!")
        print("Let me check the details...\n")
        
        # Extract booking information
        booking_info = self.ai_service.extract_booking_info(user_input)
        
        if booking_info:
            print("📝 I found these booking details:")
            for key, value in booking_info.items():
                print(f"   • {key.replace('_', ' ').title()}: {value}")
            
            # Here you would typically validate and save the booking
            print("\n✅ Your table has been reserved! We'll send a confirmation shortly.")
        else:
            print("❌ I couldn't extract the booking details. Could you please provide:")
            print("   • Number of people")
            print("   • Date and time")
            print("   • Any special requests")

def main():
    chat = RestaurantAIChat()
    asyncio.run(chat.start())

if __name__ == "__main__":
    main()
