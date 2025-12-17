import re
from typing import Set, List
import string
import time

class RelevanceFilter:
    def __init__(self, conversation_timeout=30.0):
        # Core food and restaurant keywords
        self.food_keywords = {
            # Food types
            'food', 'eat', 'eating', 'meal', 'lunch', 'dinner', 'breakfast', 'brunch', 'snack',
            'pizza', 'burger', 'sandwich', 'salad', 'soup', 'pasta', 'rice', 'noodles', 'bread',
            'chicken', 'beef', 'fish', 'seafood', 'vegetarian', 'vegan', 'meat', 'cheese',
            
            # Cuisines
            'chinese', 'italian', 'mexican', 'japanese', 'indian', 'thai', 'american', 'french',
            'korean', 'vietnamese', 'mediterranean', 'greek', 'spanish', 'lebanese', 'turkish',
            
            # Restaurant related
            'restaurant', 'cafe', 'diner', 'bistro', 'bar', 'grill', 'kitchen', 'place',
            'menu', 'order', 'ordering', 'delivery', 'takeout', 'pickup', "restaurants"
            
            # Dietary preferences
            'halal', 'kosher', 'gluten', 'dairy', 'allergic', 'allergy', 'spicy', 'mild',
            'organic', 'fresh', 'healthy', 'diet', 'keto', 'paleo',
            
            # Actions/intents
            'hungry', 'craving', 'want', 'need', 'looking', 'find', 'search', 'recommend',
            'suggest', 'show', 'tell', 'help', 'choose', 'pick', 'decide', 'taste', 'try',
            
            # Descriptors
            'delicious', 'tasty', 'yummy', 'good', 'best', 'favorite', 'love', 'like',
            'hot', 'cold', 'sweet', 'sour', 'bitter', 'salty', 'spicy', 'bland'
        }
        
        # Wake words for activation
        self.wake_words = ['bitewise', 'bite wise', 'hey bitewise', 'hi bitewise', 'hello bitewise','bitey', 'bite', 'hey bite', 'hey bitey', 'hi bite','hi bitey', 'hello bite','hello bitey','hi bitewiz', 'hello bitewiz','hello bite wiz', 'hi bite wiz','click_event','bitewiz','bite wiz']
        
        # Strong activation phrases
        self.activation_phrases = {
            'hey bitewise', 'hello bitewise', 'hi bitewise', 'bitewise',
            'excuse me', 'can you help', 'help me', 'i want to', 'i need to',
            'i want', 'i need', 'i would like', "i'd like", 'looking for',
            'find me', 'show me', 'tell me about', 'what about', 'how about',
            'where can i', 'do you have', 'any suggestions', 'recommend me',
            'i am hungry', "i'm hungry", 'feeling hungry', 'want to eat',
            'something to eat', 'place to eat', 'good food', 'best food',
            'give me', 'give me the', 'list of', 'get me'

        }
        
        # Simple greetings that should be accepted
        self.simple_greetings = {
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'hello?', 'hi?', 'hey?', 'anyone there', 'anyone here'
        }
        
        # Question words
        self.question_words = {
            'what', 'where', 'when', 'how', 'which', 'who', 'why', 'can', 'could',
            'would', 'should', 'do', 'does', 'is', 'are', 'will', 'any'
        }
        
        # Person references
        self.person_references = {
            'friend', 'friends', 'buddy', 'colleague', 'coworker', 'family',
            'mom', 'dad', 'brother', 'sister', 'wife', 'husband', 'girlfriend', 'boyfriend'
        }
        
        # Recommendation/suggestion phrases that include others
        self.recommendation_phrases = {
            'recommends', 'recommended', 'suggests', 'suggested', 'told me about',
            'says it\'s good', 'says it\'s great', 'mentioned', 'heard about',
            'friend said', 'family loves', 'everyone says', 'people say',
            'also said', 'said the', 'said it\'s', 'told us', 'told them'
        }
        
        # Background conversation indicators
        self.background_indicators = {
            'he said', 'she said', 'they said', 'we should', 'you should',
            'remember when', 'last time', 'yesterday', 'tomorrow', 'next week',
            'my friend', 'my family', 'at work', 'at home', 'at school',
            'did you see', 'have you heard', 'by the way', 'oh yeah',
            'anyway', 'so basically', 'you know what', 'speaking of',
            'keeps talking', 'won\'t stop', 'doesn\'t stop', 'very annoying',
            'stop talking', 'be quiet', 'shut up', 'just doesn\'t stop',
            'this is just', 'this just', 'it just', 'never stops',
            'so annoying', 'really annoying', 'getting annoying'
        }
        
        # Conversation enders
        self.conversation_enders = {
            'see you later', 'talk to you later', 'bye', 'goodbye', 'catch you later',
            'have a good day', 'take care', 'see ya', 'later', 'gotta go',
            'thank you', 'thanks', 'that\'s all', 'nevermind', 'cancel', 'stop', 'exit'
        }
        
        # Transliterated food words
        self.transliterated_food = {
            'khana', 'restaurant', 'hotel', 'chinese', 'desi', 'biryani', 
            'karahi', 'kebab', 'roti', 'naan', 'chai', 'lassi', 'tikka',
            'tandoor', 'curry', 'masala', 'dal', 'sabzi'
        }
        
        # Ignore patterns
        self.ignore_patterns = [
            r'^(um|uh|hmm|okay|yeah|yes|no|sure|right|oh|ah|well)+[.,!?]*$',
            r'^.{1,2}$',  # Too short (1-2 chars)
            r'^[^\w\s]+$',  # Only punctuation/symbols
            r'^(test|testing|check)[.,!?]*$',
            r'^(la)+[.,!?]*$',  # Repeated sounds
            r'^(na)+[.,!?]*$',
            r'^(.)\1{4,}',  # Repeated character 5+ times
        ]
        
        # Complaint patterns (regex)
        self.complaint_patterns = [
            r'\b(doesn\'t|does not|won\'t|will not)\s+(stop|shut up|quit)',
            r'\b(keeps?|keep)\s+(talking|going|saying)',
            r'\b(so|very|really|getting)\s+(annoying|irritating)',
            r'\bthis\s+(is\s+)?just\s+(doesn\'t|does not)',
            r'\bjust\s+(doesn\'t|does not)\s+stop',
            r'\bnever\s+stops?',
        ]
        
        # Conversation state
        self.conversation_active = False
        self.conversation_timeout = conversation_timeout
        self.last_relevant_speech_time = time.time()

    def contains_wake_word(self, text: str) -> bool:
        """Check if text contains wake word"""
        text_lower = text.lower().strip()
        return any(wake_word in text_lower for wake_word in self.wake_words)

    def clean_text(self, text: str) -> str:
        """Clean and normalize text for analysis"""
        text = re.sub(r'\s+', ' ', text.strip().lower())
        text = re.sub(r'\b(uh|um|er|ah)+\b', '', text)
        text = re.sub(r'[.!?]{2,}', '.', text)
        return text.strip()

    def has_question_structure(self, text: str) -> bool:
        """Check if text has question-like structure"""
        words = text.split()
        if not words:
            return False
            
        if words[0] in self.question_words:
            return True
        if any(word in self.question_words for word in words[:3]):
            return True
        if text.endswith('?'):
            return True
        return False

    def has_food_context(self, text: str) -> bool:
        """Check for food/restaurant context"""
        words = set(word.lower() for word in text.split())  
        return bool(words.intersection(self.food_keywords))

    def has_activation_phrase(self, text: str) -> bool:
        """Check for strong activation phrases"""
        text_lower = text.lower()  # ADD THIS LINE
        result = any(phrase in text_lower for phrase in self.activation_phrases)
        print(f"DEBUG ACTIVATION: '{text}' -> checking phrases: {result}")  # ADD DEBUG
        return result

    def is_simple_greeting(self, text: str) -> bool:
        """Check if this is a simple greeting"""
        cleaned = self.clean_text(text)
        return cleaned in self.simple_greetings

    def analyze_context_intent(self, text: str) -> dict:
        """Analyze the intent and context of the message"""
        text_lower = text.lower()
        
        return {
            'has_food_context': self.has_food_context(text),
            'has_person_reference': any(person in text_lower for person in self.person_references),
            'has_recommendation_context': any(phrase in text_lower for phrase in self.recommendation_phrases),
            'is_first_person': (' i ' in f' {text_lower} ' or text_lower.startswith('i ')),
            'is_seeking_help': any(word in text_lower for word in ['help', 'recommend', 'suggest', 'find', 'looking']),
            'is_complaint': self.seems_like_background_conversation(text),
        }

    def seems_like_background_conversation(self, text: str) -> bool:
        """Detect if this seems like background conversation"""
        # Check background indicators
        text  = text.lower()  
        if any(indicator in text for indicator in self.background_indicators):
            return True
            
        # Check conversation enders
        if any(ender in text for ender in self.conversation_enders):
            return True
        
        # Check complaint patterns
        for pattern in self.complaint_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Third person references
        third_person_patterns = [
            r'\bhe\s+(is|was|will|should|would|can|could)',
            r'\bshe\s+(is|was|will|should|would|can|could)',
            r'\bthey\s+(are|were|will|should|would|can|could)',
            r'\b(his|her|their)\s+\w+',
            r'\bthem\b', r'\bhim\b',
        ]
        
        return any(re.search(pattern, text) for pattern in third_person_patterns)

    def calculate_relevance_score(self, text: str, recent_messages: List[str] = None) -> float:
        """Calculate a relevance score from 0.0 to 1.0"""
        score = 0.0
        words = text.split()
        word_count = len(words)
        
        # Get context analysis
        context = self.analyze_context_intent(text)
        
        # Wake word gets highest priority
        if self.contains_wake_word(text):
            score += 0.9
            self.conversation_active = True
            self.last_relevant_speech_time = time.time()
            return max(0.0, min(1.0, score))
        
        # Handle "I + person + food" pattern (first-person recommendations)
        if (context['is_first_person'] and 
            context['has_person_reference'] and 
            context['has_food_context']):
            
            if context['has_recommendation_context']:
                score += 0.8
            else:
                score += 0.6
        
        # Handle third-person recommendations
        if (context['has_person_reference'] and 
            context['has_food_context'] and 
            context['has_recommendation_context']):
            score += 0.7
        
        # Strong activation phrases - ALWAYS CHECK THIS
        if self.has_activation_phrase(text):
            score += 0.8
            
        # Food context - ALWAYS CHECK THIS  
        if context['has_food_context']:
            food_word_count = sum(1 for word in words if word in self.food_keywords)
            score += min(0.6, food_word_count * 0.2)
        
        # Simple greetings
        if self.is_simple_greeting(text):
            score += 0.7
        
        # Question structure adds score
        if self.has_question_structure(text):
            score += 0.3
            
        # Proper length adds score
        if 3 <= word_count <= 20:
            score += 0.2
        elif word_count > 20:
            score -= 0.1
            
        # Strong penalty for background conversation
        if context['is_complaint']:
            score -= 0.8
            
        return max(0.0, min(1.0, score))

    def should_process_speech(self, text: str, recent_messages: List[str] = None) -> bool:
        """Main decision function - determines if speech should be processed"""
        current_time = time.time()
        dormant = False
        # Check for gibberish/noise first
        cleaned_text = self.clean_text(text)
        if not cleaned_text:
            return False , dormant
            
        for pattern in self.ignore_patterns:
            if re.match(pattern, cleaned_text):
                print(f"[FILTERED] Ignoring noise: '{text}'")
                return False , dormant
        
        # Always process wake words
        if self.contains_wake_word(text):
            self.conversation_active = True
            self.last_relevant_speech_time = current_time
            print(f"[WAKE WORD] Activating conversation: '{text}'")
            return True , dormant
        
        # Check conversation timeout
        if current_time - self.last_relevant_speech_time > self.conversation_timeout:
            self.conversation_active = False
            dormant = True
            print(f"[TIMEOUT] Conversation timed out, going dormant")

            return False , dormant
        

        # Calculate relevance
        score = self.calculate_relevance_score(text, recent_messages)
        threshold = 0.3 if self.conversation_active else 0.35
        
        is_relevant = score >= threshold
        
        print(f"Relevance check: '{text}' -> Score: {score:.2f} -> {'ACCEPT' if is_relevant else 'REJECT'}")
        
        if is_relevant:
            self.last_relevant_speech_time = current_time
            return True , dormant
        else:
            print(f"[FILTERED] Ignoring irrelevant speech: '{text}'")
            return False , dormant

    def clean_wake_word_from_text(self, text: str) -> str:
        """Remove wake words from text before sending to LLM"""
        clean_text = text
        for wake_word in self.wake_words:
            clean_text = re.sub(re.escape(wake_word), "", clean_text, flags=re.IGNORECASE).strip()
        
        # If only wake word was said, return a greeting
        if not clean_text or len(clean_text.split()) < 1:
            return "Hello"
        
        return clean_text

    def end_conversation_check(self, text: str) -> bool:
        """Check if user wants to end the conversation"""
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in self.conversation_enders):
            self.conversation_active = False
            print(f"[END] Conversation ended by user: '{text}'")
            return True
        return False

    def reset_conversation(self):
        """Manually reset conversation state"""
        self.conversation_active = False
        self.last_relevant_speech_time = time.time()
        print("[RESET] Conversation state reset")

    def get_conversation_status(self):
        """Get current conversation status for debugging"""
        current_time = time.time()
        time_since_last = current_time - self.last_relevant_speech_time
        return {
            "active": self.conversation_active,
            "time_since_last_relevant": time_since_last,
            "will_timeout_in": max(0, self.conversation_timeout - time_since_last)
        }

    # For backward compatibility with your existing code
    def is_relevant(self, text: str, threshold: float = 0.35) -> bool:
        """Backward compatibility method"""
        return self.should_process_speech(text)

    def is_relevant_with_context(self, text: str, previous_messages: List[str] = None, threshold: float = 0.35) -> bool:
        """Backward compatibility method with context"""
        return self.should_process_speech(text, previous_messages)


# Example usage and testing
if __name__ == "__main__":
    filter = RelevanceFilter()
    
    test_cases = [
        # Should ACCEPT
        ("Hello?", True),
        ("Show me the list of Italian restaurants.", True),
        ("I'm hungry, what restaurants do you recommend?", True),
        ("hey bitewise, show me some pizza places", True),
        ("I have a friend, she recommends me some chinese", True),
        ("My friend also said the Mexican is good.", True),
        ("looking for good chinese food", True),
        ("what's on the menu?", True),
        ("any vegetarian options?", True),
        
        # Should REJECT  
        ("She keeps talking. She keeps talking. It's very annoying.", False),
        ("See, this is just doesn't stop.", False),
        ("hey john, how was your day?", False),
        ("um", False),
        ("he said he's coming later", False),
        ("talking to my friend about work", False),
    ]
    
    print("Testing Enhanced Relevance Filter:")
    print("-" * 60)
    
    for text, expected in test_cases:
        result = filter.should_process_speech(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text}' -> {result} (expected {expected})")
        print()