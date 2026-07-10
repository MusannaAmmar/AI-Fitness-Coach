
from chatbot.retrieval import (
    retrieve_health_data,
    retrieve_water_logs,
    retrieve_mood_logs,
    retrieve_weight_logs,
    retrieve_meal_logs,
    retrieve_sleep_logs,
    retrieve_pain_logs,
    retrieve_medication_logs
)
from datetime import datetime, timedelta, timezone
from langchain.tools import tool


def format_timestamp_local(timestamp_str: str) -> str:
    """Convert UTC timestamp to local time (UTC+5) and format it"""
    try:
        # Parse timestamp
        if 'Z' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp_str)
            
        # Convert to UTC if naive
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        # Convert to local time (UTC+5)
        local_tz = timezone(timedelta(hours=5))
        local_dt = dt.astimezone(local_tz)
        
        return local_dt.strftime('%b %d at %I:%M %p')
    except Exception as e:
        return timestamp_str

def create_health_data_tools(user_id: str):
    """Factory function to create tools with user_id bound for each Pinecone namespace"""
    
    @tool
    def get_apple_health_data() -> str:
        """
        Retrieves Apple/Android Health synced data (steps, heart rate, sleep, calories, workouts).
        Use when user asks about: fitness metrics, activity levels, steps, heart rate, workouts, or creating fitness plans.
        """
        print(f"🔍 [TOOL] Fetching Apple Health data for user: {user_id}")
        data = retrieve_health_data(user_id)
        print(f"📊 Apple Health Data: {data}")
        
        if not data or (isinstance(data, dict) and data.get('error')):
            return "No Apple Health data found."
        
        if isinstance(data, dict):
            non_zero = [v for k, v in data.items() if k not in ['timestamp', 'error'] and v != 0.0 and v != 0]
            if not non_zero:
                return "No Apple Health data recorded yet (all metrics are zero)."
            
#             return f"""Health Metrics:
# • Steps: {data.get('steps', 0)}
# • Sleep: {data.get('sleep', 0)} hours
# • Hydration: {data.get('hydration', 0)} ml
# • Heart Rate: {data.get('heart_rate', 0)} bpm
# • Calories: {data.get('calories_burned', 0)}
# • Workouts: {data.get('workouts', 0)}
# • Last synced: {data.get('timestamp', 'N/A')}"""
        
        return f"Health: {data}"

    @tool
    def get_water_logs() -> str:
        """
        Retrieves ALL water intake logs from the water_log namespace.
        Use when user asks about: water intake, hydration, how much water they drank.
        """
        print(f"💧 [TOOL] Fetching water logs for user: {user_id}")
        logs = retrieve_water_logs(user_id)
        print(f"💧 Water logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No water intake logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"💧 WATER INTAKE LOGS ({len(logs)} entries):\n{'='*50}\n"
            total = 0
            
            for idx, log in enumerate(logs, 1):
                qty = log.get('quantity', 0)
                unit = log.get('unit', 'ml')
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {qty} {unit} - {time_str}\n"
                total += float(qty)
            
            formatted += f"\n📊 Total: {total} {unit}\n{'='*50}"
            return formatted
        
        return "No water logs found."

    @tool
    def get_weight_logs() -> str:
        """
        Retrieves ALL weight/body weight logs from the weight_logs namespace.
        Use when user asks about: weight, body weight, weight tracking, weight logs.
        """
        print(f"⚖️ [TOOL] Fetching weight logs for user: {user_id}")
        logs = retrieve_weight_logs(user_id)
        print(f"⚖️ Weight logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No weight logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"⚖️ WEIGHT LOGS ({len(logs)} entries):\n{'='*50}\n"
            
            for idx, log in enumerate(logs, 1):
                weight = log.get('quantity') or log.get('weight') or log.get('body_weight', 0)
                unit = log.get('units', log.get('unit', 'kg'))  # Only one unit
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {weight} {unit} - {time_str}\n"
            
            formatted += f"{'='*50}"
            return formatted
        
        return "No weight logs found."

    @tool
    def get_mood_logs() -> str:
        """
        Retrieves ALL mood logs from the mood_logs namespace.
        Use when user asks about: mood, feelings, emotional state, how they've been feeling.
        """
        print(f"😊 [TOOL] Fetching mood logs for user: {user_id}")
        logs = retrieve_mood_logs(user_id)
        print(f"😊 Mood logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No mood logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"😊 MOOD LOGS ({len(logs)} entries):\n{'='*50}\n"
            
            for idx, log in enumerate(logs, 1):
                mood = log.get('mood', 'N/A')
                level = log.get('mood_level', log.get('level', 'N/A'))
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {mood} (level {level}) - {time_str}\n"
            
            formatted += f"{'='*50}"
            return formatted
        
        return "No mood logs found."

    @tool
    def get_meal_logs() -> str:
        """
        Retrieves ALL meal logs from the meal_log namespace.
        Use when user asks about: meals, food, what they ate, meal tracking, nutrition logs.
        """
        print(f"🍽️ [TOOL] Fetching meal logs for user: {user_id}")
        logs = retrieve_meal_logs(user_id)
        print(f"🍽️ Meal logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No meal logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"🍽️ MEAL LOGS ({len(logs)} entries):\n{'='*50}\n"
            
            for idx, log in enumerate(logs, 1):
                meal = log.get('mealname') or log.get('meal', 'N/A')
                calories = log.get('calories', 'N/A')
                proteins=log.get('protein')
                carbs=log.get('carbs')
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {meal}"
                if calories != 'N/A':
                    formatted += f" ({calories} calories ,{proteins} proteins, {carbs} carbs)"
                formatted += f" - {time_str}\n"
            
            formatted += f"{'='*50}"
            return formatted
        
        return "No meal logs found."

    @tool
    def get_sleep_logs() -> str:
        """
        Retrieves ALL sleep logs from the sleep_log namespace.
        Use when user asks about: sleep, sleep tracking, how much they slept, sleep quality,whats their sleep log.
        """
        print(f"😴 [TOOL] Fetching sleep logs for user: {user_id}")
        logs = retrieve_sleep_logs(user_id)
        print(f"😴 Sleep logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No sleep logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"😴 SLEEP LOGS ({len(logs)} entries):\n{'='*50}\n"
            
            for idx, log in enumerate(logs, 1):
                hours = log.get('sleep')
                quality = log.get('quality', '')
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {hours} hours"
                if quality:
                    formatted += f" (quality: {quality})"
                formatted += f" - {time_str}\n"
            
            formatted += f"{'='*50}"
            return formatted
        
        return "No sleep logs found."

    @tool
    def get_pain_logs() -> str:
        """
        Retrieves ALL pain logs from the pain_log namespace.
        Use when user asks about: pain, discomfort, injuries, pain tracking, where it hurts.
        """
        print(f"🩹 [TOOL] Fetching pain logs for user: {user_id}")
        logs = retrieve_pain_logs(user_id)
        print(f"🩹 Pain logs: {logs}")
        
        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No pain logs found."
        
        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"🩹 PAIN LOGS ({len(logs)} entries):\n{'='*50}\n"
            
            for idx, log in enumerate(logs, 1):
                location = log.get('location', 'N/A')
                intensity = log.get('pain_level') or log.get('level', 'N/A')
                description = log.get('description', '')
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {location} (intensity {intensity})"
                if description:
                    formatted += f" - {description}"
                formatted += f" - {time_str}\n"
            
            formatted += f"{'='*50}"
            return formatted
        
        return "No pain logs found."
    
    @tool
    def get_medication_logs() -> str:
        """
        Retrieves ALL medication logs from the medication_log namespace.
        Use when user asks about: medications, medicine, dosage, prescription, or medication tracking.
        """
        print(f"💊 [TOOL] Fetching medication logs for user: {user_id}")
        logs = retrieve_medication_logs(user_id)
        print(f"💊 Medication logs: {logs}")

        if not logs or (isinstance(logs, dict) and logs.get('error')):
            return "No medication logs found."

        if isinstance(logs, list) and len(logs) > 0:
            formatted = f"💊 MEDICATION LOGS ({len(logs)} entries):\n{'='*50}\n"
            for idx, log in enumerate(logs, 1):
                name = log.get('medicinename', 'N/A')
                dosage = log.get('dosage', 'N/A')
                freq = log.get('frequency', 'N/A')
                timeofday = log.get('timeofday', 'N/A')
                custom = log.get('customdosage', '')
                timestamp = log.get('timestamp', 'N/A')
                
                time_str = format_timestamp_local(timestamp)
                
                formatted += f"{idx}. {name} ({dosage}, {freq}, {timeofday}"
                if custom:
                    formatted += f", custom: {custom}"
                formatted += f") - {time_str}\n"
            formatted += f"{'='*50}"
            return formatted

        return "No medication logs found."

    
    return [
        get_apple_health_data,
        get_water_logs,
        get_weight_logs,
        get_mood_logs,
        get_meal_logs,
        get_sleep_logs,
        get_pain_logs,
        get_medication_logs
    ]
