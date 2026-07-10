
from openai import OpenAI
from dotenv import load_dotenv
import os
from langgraph.store.memory import InMemoryStore
import uuid
from datetime import datetime, timedelta, timezone
from utils import db_client, get_user_by_id

from langchain.agents import create_agent
from langgraph.checkpoint.mongodb import MongoDBSaver
import re
from chatbot.tools import create_health_data_tools


DB_URI=os.getenv('MONGODB_URI')

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)
# memory = InMemoryStore()
memory_ns=MongoDBSaver.from_conn_string(DB_URI)
memory=memory_ns.__enter__()


class FitnessCoach:
    def __init__(self, session_id, user_id):
        """
        Initialize FitnessCoach
        
        Args:
            session_id: Unique session identifier
            user_id: Can be either:
                - A string: '507f1f77bcf86cd799439011'
                - A dict: {'_id': '507f1f77bcf86cd799439011', 'fullName': 'John'}
        """
        self.session_id = session_id
        self.checkpointer = memory
        self.user_id = user_id
        self.max_history_messages = 20
        self.conversation_summary = ""
        self.messages_since_summary = 0
        self.summarize_threshold = 10
        self.config={
            "configurable": {
                "thread_id": session_id,
                "checkpoint_ns": "default"
            }
        }
        
        # Load conversation history
        self.load_history_from_db_to_memory()
        
        # Create tools with user_id bound and initialize agent
        user_id_str = self.get_user_id_str()
        self.tools = create_health_data_tools(user_id_str)
        self.agent = self._create_agent()

    def get_user_id_str(self):
        """
        Return user_id as string, handling both dict and string formats.
        
        Examples:
            - String input: '507f1f77bcf86cd799439011' → '507f1f77bcf86cd799439011'
            - Dict input: {'_id': '507f1f77bcf86cd799439011'} → '507f1f77bcf86cd799439011'
        """
        if isinstance(self.user_id, dict):
            # Handle dict format with _id key
            if '_id' in self.user_id:
                return str(self.user_id['_id'])
            # Handle dict format with id key
            elif 'id' in self.user_id:
                return str(self.user_id['id'])
            # Fallback: return the whole dict as string (shouldn't happen)
            # return str(self.user_id)
            return None
        # Already a string
        return str(self.user_id)
    
    def get_user_name(self):
        """
        Extract user name from user_id if available, otherwise return 'there'
        
        Examples:
            - Dict with name: {'_id': '...', 'fullName': 'John'} → 'John'
            - String or dict without name: → 'there'
        """
        if isinstance(self.user_id, dict):
            # Try different possible name keys
            return (
                self.user_id.get('fullName') or 
                self.user_id.get('name') or 
                self.user_id.get('username') or 
                'there'
            )
        return 'there'
    
    def _create_agent(self):
        """Create LangChain agent with tools and system prompt using new API"""
        user_name = self.get_user_name()
        
        system_prompt = f"""You are an AI fitness coach named FitCoach, having a natural conversation with {user_name}.

🎯 YOUR ROLE:
You're a specialized fitness and health coach. You ONLY discuss topics related to:
- Fitness, exercise, and workout routines
- Nutrition, diet, and meal planning
- Health metrics and wellness
- Sleep, recovery, and stress management
- Weight management and body composition
- Mental health as it relates to fitness

🚫 STRICT BOUNDARIES:
- DO NOT answer questions about politics, current events, celebrities, entertainment, technology, or any non-health topics
- If asked about unrelated topics (like "who is the president", "what's the weather", etc.), politely redirect:
  "I'm your fitness coach, so I focus specifically on health and fitness topics. Is there anything about your workouts, nutrition, or wellness I can help you with?"
- DO NOT recommend or mention other fitness apps, trackers, or competing services (MyFitnessPal, Strava, Fitbit app, etc.)
- If users ask about other fitness apps, redirect them to this app's features:
 "Great news - you're already in the perfect app! Right here you can track your water intake, meals, weight, mood, sleep, medications, and pain. Plus, we sync with Apple Health and Google Fit for your steps, heart rate, and workouts. And you have me as your personal AI coach! What would you like to start tracking today?"
- NEVER suggest downloading other apps or using external fitness platforms - this app has everything they need!

🔧 YOUR CAPABILITIES:
You have access to 8 specialized tools, each querying a specific data source:
1. **get_apple_health_data** - Apple/Android Health synced metrics (steps, heart rate, sleep, calories, workouts)
2. **get_water_logs** - Water intake logs from water_log namespace
3. **get_weight_logs** - Weight tracking logs from weight_logs namespace
4. **get_mood_logs** - Mood/emotional logs from mood_logs namespace
5. **get_meal_logs** - Meal/nutrition logs from meal_log namespace
6. **get_sleep_logs** - Sleep tracking logs from sleep_log namespace
7. **get_pain_logs** - Pain level logs from pain_log namespace
8. **get_medication_logs** - Medication logs from medication_log namespace

Each tool directly queries its Pinecone namespace - no filtering needed!

📊 WHEN TO USE TOOLS:
⚠️ CRITICAL: Use the EXACT tool that matches the user's question!

**Tool Selection Guide:**
- "water/hydration/drink" → get_water_logs
- "weight/body weight/scale" → get_weight_logs  
- "mood/feeling/emotional/how am I feeling" → get_mood_logs
- "meal/food/ate/nutrition" → get_meal_logs
- "sleep/slept/rest" → get_sleep_logs
- "medication/medicine/dosage/prescription" → get_medication_logs
- "pain/pain-level/hurt/injury/discomfort" → get_pain_logs
- "steps/heart rate/workout/fitness metrics" → get_apple_health_data
- "fitness plan/workout plan" → get_apple_health_data (check metrics first)

**Examples:**
- "how much water today?" → get_water_logs
- "what's my weight?" → get_weight_logs
- "how am I feeling?" → get_mood_logs
- "what did I eat?" → get_meal_logs
- "what medications am I taking?" → get_medication_logs
- "tell me my medication"-> get_medication_logs
- "create a workout plan" → get_apple_health_data

IMPORTANT: Each tool queries its own Pinecone namespace directly - no cross-contamination!

🔎 MOOD LOG LEVELS - MEMORIZE THIS EXACTLY:
When interpreting mood logs, use this EXACT mapping (this is the app's standard):
- Level 1 = Sad (not average, not neutral - SAD)
- Level 2 = Average (not neutral - AVERAGE)
- Level 3 = Neutral (middle ground - NEUTRAL)
- Level 4 = Happy (not neutral - HAPPY)
- Level 5 = Excited (highest mood - EXCITED, not average!)

⚠️ CRITICAL: Level 5 is EXCITED (best mood), NOT average or neutral!
When you see mood_level: 5, ALWAYS say the user was "excited" or "feeling great"
When you see mood_level: 1, ALWAYS say the user was "sad" or "feeling down"

Examples:
- mood_level: 1 → "You were feeling sad"
- mood_level: 2 → "Your mood was average"
- mood_level: 3 → "You felt neutral"
- mood_level: 4 → "You were happy"
- mood_level: 5 → "You were excited!" or "You were feeling great!"

💪 FITNESS PLAN RECOMMENDATIONS:
When creating plans, analyze the data:
- Sleep <6h or elevated HR → Light recovery workout (yoga, walking, stretching)
- Sleep 6-7h or low hydration → Moderate intensity (light cardio, bodyweight exercises)
- Sleep 7-9h + normal vitals → Full intensity (strength training, HIIT, heavy lifting)
- High step count (15k+) multiple days → Rest day or active recovery
- Low activity (<5k steps) → Encourage movement and light cardio
- Weight/mood changes → Adjust intensity and provide mental health support

When analyzing mood:
- Mood level 1-2 (sad/average) → Suggest light exercise to boost mood (walking, yoga)
- Mood level 3 (neutral) → Regular workout routine
- Mood level 4-5 (happy/excited) → Capitalize on high energy with challenging workouts

🏋️ EXERCISE & HEALTH GUIDANCE:
If users ask general health questions (like "how to be healthy"), provide practical advice:
- Recommend daily exercise routines (cardio, strength training, flexibility)
- Suggest 7-9 hours of quality sleep
- Advise 8-10 glasses of water daily
- Encourage balanced nutrition with whole foods
- Recommend stress management through exercise, meditation, or yoga
- **Suggest tracking their metrics IN THIS APP** - emphasize they can log water, meals, mood, sleep, weight, pain, and medications right here!

📱 THIS APP'S FEATURES (mention when relevant):
- Water intake tracking
- Meal and calorie logging
- Weight tracking over time
- Mood journaling (5-level scale)
- Sleep duration tracking
- Pain level monitoring
- Medication schedule tracking
- Apple Health/Google Fit sync (steps, heart rate, workouts, calories)
- AI fitness coaching (that's you!)

💬 CONVERSATION STYLE:
- Be warm, encouraging, and conversational
- Use {user_name}'s name occasionally for personal touch
- Keep responses 150-250 words (concise but complete)
- Use 1-2 emojis maximum for friendliness
- Ask follow-up questions to understand goals better
- Reference specific metrics when giving advice ("I see you were feeling excited yesterday with a mood level of 5...")
- **When showing logs, ALWAYS list individual entries with their times, not just totals**
- For meal logs show meal name and then in brackets show nutrition of that meal like(calorie,proteins,carbs)
- Celebrate wins and progress!
- You may reference previous user questions and your own responses when asked about earlier conversation.
- When interpreting mood data, ALWAYS use the correct level mapping (1=Sad, 5=Excited)

⚠️ IMPORTANT:
- Stay strictly within fitness and health topics
- Always check tools BEFORE making fitness plans
- Don't make assumptions - use actual data
- If no data available, ask user about their current state
- Be supportive even with incomplete data
- Redirect off-topic questions back to fitness and health
- NEVER recommend other fitness apps - promote THIS app's features instead
- When interpreting mood_level, use the EXACT mapping: 1=Sad, 2=Average, 3=Neutral, 4=Happy, 5=Excited

⚡️ RESPONSE STYLE (CRITICAL - FOLLOW EXACTLY):
🚫 BANNED FORMATTING - NEVER USE:
- NO bullet points (-, *, •)
- NO numbered lists (1., 2., 3.)
- NO headings or bold (**text**)
- NO asterisks for emphasis
- NO colons followed by lists (like "Mood: ..." or "Steps: ...")
- NO line breaks between topics
- NO phrases like "Here's a summary" or "Here's what I found"

✅ REQUIRED STYLE:
- Write in PLAIN flowing sentences like you're texting a friend
- Combine all information into natural paragraphs
- Use "and" or "also" to connect ideas smoothly
- Keep it to 2-4 short sentences maximum
- Sound warm and conversational, not like a report or summary

🎯 HANDLING APP RECOMMENDATIONS:
If user asks "what app should I use for fitness/tracking?":
❌ DON'T say: "You could try MyFitnessPal or Strava..."
✅ DO say: "Great news - you're already in the perfect app! Right here you can track your water intake, meals, weight, mood, sleep, medications, and pain. Plus, we sync with Apple Health and Google Fit for your steps, heart rate, and workouts. And you have me as your personal AI coach! What would you like to start tracking today?"

Remember: You're a specialized fitness coach built into THIS app, not a general assistant. Keep the conversation focused on helping {user_name} achieve their health and fitness goals using the features available right here!"""

        # Create agent using new LangChain API
        agent = create_agent(
            model="gpt-4o",
            tools=self.tools,
            system_prompt=system_prompt
        )
        
        return agent
    
    def _get_message_history(self):
        """Convert stored messages to the format expected by new agent API"""
        try:
            db = db_client['fitnessApp']
            chat_history_collection = db['chat_history']
            
            query = {
                'session_id': self.session_id,
                'user_id': self.get_user_id_str()
            }
            
            cursor = chat_history_collection.find(query).sort('timestamp', 1).limit(self.max_history_messages)
            
            messages = []
            for item in cursor:
                content = item.get('content', '').strip()
                if not content or content.lower() in ['none', 'none.']:
                    continue
                
                role = item.get('role')
                if role == 'user':
                    messages.append({"role": "user", "content": content})
                elif role == 'assistant':
                    messages.append({"role": "assistant", "content": content})
            
            return messages
        except Exception as e:
            print(f"Error loading history: {str(e)}")
            return []
    
    def save_message(self, role, content):
        """Save message to memory and database"""
        try:
            if not content or content.strip() == "":
                print(f"Warning: Attempted to save empty {role} message")
                return None
            
            message_id = str(uuid.uuid4())
            message_content = {
                'role': role,
                'content': content,
                'session_id': self.session_id,
                'user_id': self.get_user_id_str(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Save to in-memory store
            # memory.put(
            #     namespace=self.name_space,
            #     key=message_id,
            #     value=message_content
            # )
            self.checkpointer.put(
                self.config,
                checkpoint={
                    'id':message_id,
                    'v':1,
                    'channel_values':message_content
                },
                metadata={},
                new_versions={}

            )

            # Save to MongoDB
            try:
                db = db_client['fitnessApp']
                chat_history = db['chat_history']
                chat_history.insert_one(message_content)
            except Exception as db_e:
                print(f"MongoDB saving failed: {str(db_e)}")

            if role == 'assistant':
                self.messages_since_summary += 1
            
            return message_content
        except Exception as e:
            print(f'Memory saving failed: {str(e)}')
            return None
        
   
    
    def chat(self, user_message):
        """
        Main chat method using new LangChain agent API for conversational fitness coaching
        """
        try:
            if not user_message or user_message.strip() == "":
                return {
                    "response": "Please provide a message.",
                    "error": "Empty message"
                }
            
            print(f"\n💬 User: {user_message}")
            
            # Save user message
            self.save_message('user', user_message)
            
            # Get conversation history
            message_history = self._get_message_history()
            
            # Add current user message to the messages array
            # current_messages = message_history + [{"role": "user", "content": user_message}]
            if self.conversation_summary:
                current_messages = [{"role": "system", "content": self.conversation_summary}] + message_history + [{"role": "user", "content": user_message}]
            else:
                current_messages = message_history + [{"role": "user", "content": user_message}]
            
            # Run agent with new API
            result = self.agent.invoke({"messages": current_messages},config=self.config)
            
            # Extract response from result
            # The new agent returns messages in result["messages"]
            assistant_response = ""
            if isinstance(result, dict) and "messages" in result:
                # Get the last message (assistant's response)
                last_message = result["messages"][-1]
                if hasattr(last_message, 'content'):
                    assistant_response = last_message.content
                elif isinstance(last_message, dict):
                    assistant_response = last_message.get('content', '')
            
            assistant_response = assistant_response.strip()
            # assistant_response = self.clean_message(assistant_response)
            
            if not assistant_response:
                assistant_response = "I apologize, but I couldn't generate a proper response. Could you please rephrase your question?"
            
            print(f"🤖 Assistant: {assistant_response[:200]}...")
            
            # Save assistant response
            self.save_message('assistant', assistant_response)
            
            # Summarize if needed
            if self.messages_since_summary >= self.summarize_threshold:
                self.summarize_conversation()
            
              # Extract total tokens used (if available)
            total_tokens = 0
            if isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1]
                # Get assistant response
                if hasattr(last_message, 'content'):
                    assistant_response = last_message.content
                elif isinstance(last_message, dict):
                    assistant_response = last_message.get('content', '')
                # Get total tokens from response_metadata
                response_metadata = getattr(last_message, 'response_metadata', None) or last_message.get('response_metadata', {})
                if response_metadata and 'token_usage' in response_metadata:
                    total_tokens = response_metadata['token_usage'].get('total_tokens', 0)
        
            return {
                "response": assistant_response,
                "success": True,
                "total_tokens": total_tokens

            }
            
        except Exception as e:
            error_message = f"Error in chat: {str(e)}"
            print(f"❌ {error_message}")
            return {
                "response": "I apologize, but I encountered an error. Please try again.",
                "error": error_message,
                "success": False
            }
    
    def summarize_conversation(self):
        """Summarize older conversation to reduce token usage"""
        try:
            all_messages = self.load_history_from_db_to_memory()
            if all_messages is None or len(all_messages) < self.summarize_threshold:
                return
            
            messages_to_summarize = all_messages[:-self.max_history_messages]
            
            if not messages_to_summarize:
                return
            
            conversation_text = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}" 
                for msg in messages_to_summarize
            ])
            
            summary_prompt = f"""Summarize this fitness coaching conversation concisely. Include:
1. User's fitness goals
2. Key health metrics discussed
3. Workout plans or recommendations given
4. Progress or challenges mentioned
5. Important preferences or restrictions

Keep under 150 words.

CONVERSATION:
{conversation_text}"""
            
            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': summary_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            self.conversation_summary = response.choices[0].message.content.strip()
            self.messages_since_summary = 0
            
            print(f"\n💾 Conversation summarized!\n")
            return self.conversation_summary
        except Exception as e:
            print(f'Summarization failed: {str(e)}')
    
    def get_paginated_history_from_db(self, page: int = 1, page_size: int = 10):
        """Get paginated conversation history from MongoDB"""
        try:
            db = db_client['fitnessApp']
            chat_history = db['chat_history']

            query = {
                'session_id': self.session_id,
                'user_id': self.get_user_id_str()
            }

            skip = (page - 1) * page_size
            total_count = chat_history.count_documents(query)

            cursor = chat_history.find(query).sort('timestamp', -1).skip(skip).limit(page_size)

            messages = []
            for item in cursor:
                messages.append({
                    'role': item.get('role'),
                    'content': item.get('content'),
                    'timestamp': item.get('timestamp')
                })

            messages.reverse()

            return {
                'messages': messages,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_messages': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }
        except Exception as e:
            print(f'Error retrieving paginated messages: {str(e)}')
            return {
                'messages': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_messages': 0,
                    'total_pages': 0
                },
                'error': str(e)
            }

    def load_history_from_db_to_memory(self):
        """Load conversation history from MongoDB into memory"""
        try:
            messages = []
            db = db_client['fitnessApp']
            chat_history = db['chat_history']

            query = {
                'session_id': self.session_id,
                'user_id': self.get_user_id_str()
            }

            cursor = chat_history.find(query).sort('timestamp', 1)

            for item in cursor:
                message_id = str(uuid.uuid4())
                # memory.put(
                #     namespace=self.name_space,
                #     key=message_id,
                    # value={
                    #     'role': item.get('role'),
                    #     'content': item.get('content'),
                    #     'session_id': item.get('session_id'),
                    #     'user_id': item.get('user_id'),
                    #     'timestamp': item.get('timestamp')
                    # }
                # )

                value={
                        'role': item.get('role'),
                        'content': item.get('content'),
                        'session_id': item.get('session_id'),
                        'user_id': item.get('user_id'),
                        'timestamp': item.get('timestamp')
                    }


                self.checkpointer.put(
                    self.config,
                    checkpoint={
                        'id':message_id,
                        'v':1,
                        'channel_values':value

                    },
                    metadata={},
                    new_versions={}

                )
                messages.append({
                    'role': item.get('role'),
                    'content': item.get('content'),
                    'timestamp': item.get('timestamp')
                })

            message_count = chat_history.count_documents(query)
            print(f"✅ Loaded {message_count} messages from DB to memory")
           
            return messages
        except Exception as e:
            print(f'❌ Error loading history from DB: {str(e)}')
            return []