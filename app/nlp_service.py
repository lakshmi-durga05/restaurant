import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

class RestaurantNLPService:
    def __init__(self):
        # Common restaurant section keywords
        self.section_keywords = {
            "lake view": ["lake", "water", "lakeview", "lakeside", "waterfront"],
            "garden view": ["garden", "outdoor", "patio", "terrace", "gardenview"],
            "normal": ["indoor", "inside", "normal", "regular", "standard"]
        }
        
        # Time patterns
        self.time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",  # 7:30, 7:30pm
            r"(\d{1,2})\.(\d{2})\s*(am|pm)?",  # 8.30, 8.30pm
            r"(\d{1,2})\s*(am|pm)",  # 7pm, 7 am
            r"(\d{1,2})\s*o'clock",  # 7 o'clock
            r"(\d{1,2})\s*oclock",   # 7 oclock
            r"(\d{1,2})\s*(\d{2})\s*(am|pm)",  # 8 30 pm
        ]
    
    def parse_reservation_request(self, text: str) -> Dict:
        """Parse natural language reservation request and extract structured information"""
        text = text.lower().strip()
        
        # Extract party size
        party_size = self._extract_party_size(text)
        
        # Extract date
        date = self._extract_date(text)
        
        # Extract time
        time = self._extract_time(text)
        
        # Extract section preference
        section_preference = self._extract_section_preference(text)
        
        # Extract customer name (if mentioned)
        customer_name = self._extract_customer_name(text)
        
        return {
            "party_size": party_size,
            "date": date,
            "time": time,
            "section_preference": section_preference,
            "customer_name": customer_name,
            "original_text": text
        }
    
    def _extract_party_size(self, text: str) -> Optional[int]:
        """Extract party size from text"""
        # Look for explicit numbers
        patterns = [
            r"(\d+)\s*(?:people|guests|persons|seats?)",
            r"table\s*for\s*(\d+)",
            r"reservation\s*for\s*(\d+)",
            r"(\d+)\s*(?:person|guest|seat)",
            r"(\d+)\s*(?:of\s*us|people|guests)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                size = int(match.group(1))
                if 1 <= size <= 20:  # Reasonable party size
                    return size
        
        # Look for standalone numbers that might be party size
        numbers = re.findall(r'\b(\d+)\b', text)
        for num in numbers:
            size = int(num)
            if 1 <= size <= 20:
                # Check if it's not part of time or date
                if not self._is_time_or_date_number(text, num):
                    return size
        
        return None
    
    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract date from text"""
        # Look for explicit date mentions
        date_patterns = [
            r"(today|tonight)",
            r"(tomorrow|tmr|tmrw)",
            r"(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))",
            r"(\d{1,2})[/-](\d{1,2})",  # MM/DD or DD/MM
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # MM/DD/YYYY
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})",
            r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)"
        ]
        
        today = datetime.now()
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                if pattern == r"(today|tonight)":
                    return today
                elif pattern == r"(tomorrow|tmr|tmrw)":
                    return today + timedelta(days=1)
                elif "next" in pattern:
                    # Handle "next monday" etc.
                    day_name = match.group(1).split()[-1]
                    return self._get_next_day(day_name)
                elif len(match.groups()) == 2:
                    # Handle MM/DD or month day
                    try:
                        if any(month in text.lower() for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']):
                            # Month day format
                            month_name = match.group(1) if match.group(1).isdigit() else match.group(2)
                            day = match.group(2) if match.group(1).isdigit() else match.group(1)
                            return self._parse_month_day(month_name, day, today.year)
                        else:
                            # MM/DD format - assume current year
                            month, day = int(match.group(1)), int(match.group(2))
                            if 1 <= month <= 12 and 1 <= day <= 31:
                                return datetime(today.year, month, day)
                    except:
                        continue
        
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Extract time from text"""
        for pattern in self.time_patterns:
            match = re.search(pattern, text)
            if match:
                if ":" in pattern or "." in pattern:
                    hour, minute = int(match.group(1)), int(match.group(2))
                    ampm = match.group(3) if len(match.groups()) > 2 else None
                else:
                    hour = int(match.group(1))
                    minute = 0
                    ampm = match.group(2) if len(match.groups()) > 1 else None
                
                # Handle AM/PM
                if ampm:
                    if ampm.lower() == "pm" and hour != 12:
                        hour += 12
                    elif ampm.lower() == "am" and hour == 12:
                        hour = 0
                
                # Validate time
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
        
        # Fallback: try to parse complex time formats manually
        try:
            # Look for time-like patterns in the text
            time_words = re.findall(r'\b(\d{1,2}(?:[.:]\d{2})?\s*(?:am|pm)?)\b', text.lower())
            for time_word in time_words:
                # Clean up the time string
                time_str = time_word.strip()
                if '.' in time_str and ('pm' in time_str or 'am' in time_str):
                    # Handle "8.30pm" format
                    time_str = time_str.replace('.', ':')
                
                # Try to parse manually
                try:
                    if ':' in time_str:
                        if 'pm' in time_str:
                            time_part = time_str.replace('pm', '').strip()
                            hour, minute = map(int, time_part.split(':'))
                            if hour != 12:
                                hour += 12
                        elif 'am' in time_str:
                            time_part = time_str.replace('am', '').strip()
                            hour, minute = map(int, time_part.split(':'))
                            if hour == 12:
                                hour = 0
                        else:
                            hour, minute = map(int, time_str.split(':'))
                        
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            return f"{hour:02d}:{minute:02d}"
                except:
                    continue
        except:
            pass
        
        return None
    
    def _extract_section_preference(self, text: str) -> Optional[str]:
        """Extract restaurant section preference from text"""
        for section, keywords in self.section_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return section
        
        # Check for "any" or "doesn't matter"
        if any(word in text for word in ["any", "doesn't matter", "don't care", "flexible"]):
            return "any"
        
        return None
    
    def _extract_customer_name(self, text: str) -> Optional[str]:
        """Extract customer name from text (basic implementation)"""
        # Look for "I'm" or "my name is" patterns
        patterns = [
            r"i'?m\s+([a-zA-Z\s]+)",
            r"my\s+name\s+is\s+([a-zA-Z\s]+)",
            r"this\s+is\s+([a-zA-Z\s]+)",
            r"([a-zA-Z\s]+)\s+here"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if len(name) > 1:  # Avoid single letters
                    return name.title()
        
        return None
    
    def _is_time_or_date_number(self, text: str, number: str) -> bool:
        """Check if a number is part of time or date"""
        # Look for context around the number
        context = text[max(0, text.find(number)-5):text.find(number)+len(number)+5]
        
        time_indicators = ["pm", "am", "o'clock", "oclock", ":", "hour"]
        date_indicators = ["january", "february", "march", "april", "may", "june", 
                          "july", "august", "september", "october", "november", "december",
                          "/", "-", "date"]
        
        return any(indicator in context.lower() for indicator in time_indicators + date_indicators)
    
    def _get_next_day(self, day_name: str) -> datetime:
        """Get next occurrence of a specific day of the week"""
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        target_day = days.index(day_name.lower())
        current_day = datetime.now().weekday()
        
        days_ahead = target_day - current_day
        if days_ahead <= 0:
            days_ahead += 7
        
        return datetime.now() + timedelta(days=days_ahead)
    
    def _parse_month_day(self, month_name: str, day: str, year: int) -> datetime:
        """Parse month day format"""
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        
        if month_name.isdigit():
            month = int(month_name)
        else:
            month = months.get(month_name.lower(), 1)
        
        day = int(day)
        return datetime(year, month, day)
    
    def generate_friendly_response(self, parsed_data: Dict, available: bool = True) -> str:
        """Generate a friendly, natural response based on parsed data"""
        if not available:
            return "I'm sorry, but I couldn't find a table matching your request. Could you please provide more details?"
        
        response_parts = []
        
        if parsed_data.get("customer_name"):
            response_parts.append(f"Hello {parsed_data['customer_name']}!")
        
        response_parts.append("Let me check availability for you.")
        
        if parsed_data.get("party_size"):
            response_parts.append(f"For {parsed_data['party_size']} people")
        
        if parsed_data.get("date"):
            date_str = parsed_data["date"].strftime("%A, %B %d")
            response_parts.append(f"on {date_str}")
        
        if parsed_data.get("time"):
            response_parts.append(f"at {parsed_data['time']}")
        
        if parsed_data.get("section_preference") and parsed_data["section_preference"] != "any":
            response_parts.append(f"in our {parsed_data['section_preference'].title()} section")
        
        response_parts.append(".")
        
        return " ".join(response_parts)
