from openai import OpenAI
import os
import json
import time
import uuid
from dotenv import load_dotenv
from fitness_file.embedding_service import EmbeddingService
from fitness_file.schema import WorkoutPlanContainer
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from utils import embedding_service
from langchain.tools import tool
from langchain.agents import create_agent
from typing import List, Dict, Any, Optional
import re
from datetime import datetime, timedelta
import random  # For generating random IDs in prompts


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)


def create_database_tools(user_id):
    @tool
    def fetch_exercises_from_database(query: str = "fitness workout exercises training") -> List[Dict]:
        """
        Fetch exercises from the vector database based on similarity search.
        Use this tool to get available exercises for workout plan creation.
        
        Args:
            query: Search query to find relevant exercises (default: general fitness query)
        
        Returns:
            List of exercise dictionaries with metadata
        """
        try:
            print(f"[TOOL CALLING] fetch_exercises_from_database for user {user_id} called with query:", query)

            exercises_list = []
            similar_searches = embedding_service.search_similar(
                query_text=query,
                top_k=10,
                namespace='exercises'
            )
            
            for search_result in similar_searches:
                if hasattr(search_result, 'metadata') and search_result.metadata:
                    exercise_data = dict(search_result.metadata)
                    exercise_id = getattr(search_result, 'id', None)
                    if exercise_id is not None:
                        exercise_data['exercise_id'] = exercise_id
                    exercises_list.append(exercise_data)
            
            return exercises_list
        except Exception as e:
            raise Exception(f"Database connector failed: {str(e)}")

    @tool
    def get_previous_workout_summary(user_specific_query: str = "previous workout summaries") -> Optional[List[Dict]]:
        """
        Retrieve the user's MOST RECENT weekly workout plan summaries from vector database.
        Use this tool to check if the user has previous workout history to build upon.

        Args:
            user_specific_query: Additional query context (optional)

        Returns:
            List of previous workout summaries with day, body_parts, and summary fields,
            or None if no previous workouts found for this specific user
        """
        try:
            print(f"[TOOL CALLING] get_previous_workout_summary for user_id: {user_id}")
            print(f"[TOOL CALLING] Query: {user_specific_query}")

            query_text = f"{user_id} workout plan {user_specific_query}".strip()
            previous_results = embedding_service.search_similar(
                query_text=query_text,
                top_k=1000,  # REDUCED: From 1000 to 50 to avoid massive prompts/token limits
                namespace='workout_summaries'
            )

            if not previous_results or len(previous_results) == 0:
                print("[TOOL RESULT] No results found in vector database")
                return None

            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)

            previous_week_summary = []
            user_data_found = False

            for result in previous_results:
                metadata = getattr(result, "metadata", None) or result.get("metadata", {})
                if not metadata or metadata.get('user_id') != user_id:
                    continue
                user_data_found = True

                workout_date_str = metadata.get('date') or metadata.get('created_at')
                if workout_date_str:
                    try:
                        workout_date = datetime.fromisoformat(workout_date_str.replace('Z', '+00:00'))
                        if not (last_monday.date() <= workout_date.date() <= last_sunday.date()):
                            continue
                    except Exception:
                        continue

                day_summary = {
                    "day": metadata.get("day"),
                    "body_parts": metadata.get("body_parts"),
                    "exercise_id": metadata.get("exercise_id"),
                    "summary": metadata.get("summary"),
                    "date": metadata.get("date") or metadata.get("created_at"),
                }
                if day_summary.get("day") and day_summary.get("summary"):
                    previous_week_summary.append(day_summary)

            if not user_data_found or not previous_week_summary:
                return None

            day_order = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                         "Friday": 5, "Saturday": 6, "Sunday": 7}
            previous_week_summary.sort(key=lambda x: day_order.get(x.get("day", ""), 8))

            return previous_week_summary

        except Exception as e:
            print(f"[ERROR] Error fetching previous workout summary: {e}")
            return None

    return [fetch_exercises_from_database, get_previous_workout_summary]


def prepare_batch_request_data(user_id: str) -> Dict[str, Any]:
    """
    Prepare all necessary data for a single user's batch request.
    This function gathers exercise database and previous workout data upfront.
    
    Args:
        user_id: User identifier
    
    Returns:
        Dictionary containing exercises, previous workouts, and user context
    """
    try:
        print(f"📝 Preparing batch data for user: {user_id}")
        
        # Create tools to fetch data
        tools = create_database_tools(user_id)
        exercise_tool = tools[0]
        previous_workout_tool = tools[1]
        
        # Fetch exercises from database
        exercises = exercise_tool.invoke({"query": "fitness workout exercises training"})
        print(f"✅ Fetched {len(exercises)} exercises from database")
        
        # Fetch previous workout summaries
        previous_workouts = previous_workout_tool.invoke({"user_specific_query": "previous workout summaries"})
        print(f"✅ Fetched previous workouts: {len(previous_workouts) if previous_workouts else 0}")
        
        return {
            "user_id": user_id,
            "exercises": exercises,
            "previous_workouts": previous_workouts
        }
    
    except Exception as e:
        print(f"❌ Error preparing batch data for user {user_id}: {str(e)}")
        raise


def create_batch_prompt(user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create a single chat completion prompt (messages) for the Batch API.
    Embeds all fetched data directly into the prompt to avoid tool calls.
    
    Args:
        user_data: Prepared data from prepare_batch_request_data
    
    Returns:
        List of messages for the chat completion
    """
    user_id = user_data["user_id"]
    exercises = user_data["exercises"]
    previous_workouts = user_data["previous_workouts"] or []

    # Format exercises as JSON string for prompt
    exercises_json = json.dumps(exercises, indent=2)

    # Format previous workouts as JSON string for prompt (limit to avoid token overflow)
    if len(previous_workouts) > 20:  # Further limit if still too many after top_k=50
        previous_workouts = previous_workouts[:20]
        print(f"⚠️ Truncated previous workouts to 20 for user {user_id} to fit token limits")
    previous_json = json.dumps(previous_workouts, indent=2)

    # Check prompt size roughly (in characters; ~4 chars/token)
    prompt_size = len(exercises_json) + len(previous_json)
    if prompt_size > 100000:  # Rough threshold for ~25k tokens
        print(f"⚠️ Warning: Large prompt for user {user_id} ({prompt_size} chars). May hit token limits.")

    system_prompt = f"""You are a professional fitness trainer AI assistant that creates personalized weekly workout plans.

IMPORTANT: You MUST follow this workflow in order:

STEP 1: CHECK PREVIOUS WORKOUT HISTORY
- Analyze the previous workout data provided below to understand:
  * Which body parts were trained and on which days
  * Any rest days or recovery patterns
- If previous data exists, create a progressive plan that:
  * Continues from where the previous week ended
  * Increases volume/intensity appropriately (progressive overload)
  * Maintains similar body part split unless user requested changes
  * Varies exercises while keeping similar movement patterns

STEP 2: USE PROVIDED EXERCISES
- CRITICAL: You MUST use ONLY the complete exercise data provided below
- DO NOT invent any exercise data
- Match exercises to the body parts from previous plan or new requirements

STEP 3: CREATE WORKOUT PLAN
- Design a comprehensive 7-day workout plan based on:
  * Previous workout context (if available) - USE ONLY for understanding progression and body part split
  * User's fitness level (assume Intermediate unless specified)
  * Progressive overload principles
  * Exercise variety and balance
- CRITICAL: For EVERY exercise in the plan, you MUST use the COMPLETE data from the provided exercises
- NEVER leave any required fields as null or empty


USER INFORMATION:
- User ID: {user_id}

PREVIOUS WORKOUTS DATA:
{previous_json}

AVAILABLE EXERCISES DATA:
{exercises_json}

CRITICAL VALIDATION RULES:
- For EVERY day, you MUST include a minimum of 3 and a maximum of 5 exercises.
- NEVER generate fewer than 3 or more than 5 exercises for any day.
- If fewer than 3 exercises available for a body part, select additional from other relevant body parts to reach at least 3 per day.
- You MUST validate the final plan before returning: each day must have between 3 and 5 exercises, no exceptions.

Return JSON with "weeklyPlan" array containing 7 workoutPlan objects:
- weeklyPlan: Array of workout objects
  - workoutPlan: Object containing:
    - id: "wp_" + 8 random digits
    - day: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday
    - title: Descriptive name based on body parts
    - date: {datetime.now().isoformat()}
    - durationMinutes: 30-60 minutes
    - level: Beginner, Intermediate, or Advanced
    - category: Body part from exercises
    - notes: Training tip about form and rest periods
    - exercises: Array of exercise objects (ALL fields REQUIRED - NO null values allowed):
      - id: MUST use exercise_id from provided exercises
      - bodyParts: MUST use body_parts from provided exercises
      - equipments: MUST use equipment from provided exercises
      - instructions: MUST use instructions from provided exercises (use empty string "" if null)
      - gifUrl: MUST use gif_url from provided exercises (use empty string "" if null)
      - name: MUST use exact name from provided exercises
      - summary: REQUIRED. Brief 1-2 sentence summary of this exercise's role and focus in today's workout.
      - secondaryMuscles: MUST use secondary_muscles from provided exercises (use empty string "" if null)
      - targetMuscles: MUST use target_muscles from provided exercises (use empty string "" if null)
      - sets: 2-5 sets based on fitness level (REQUIRED integer)
      - repsRange: REQUIRED string - "12-15" for Beginner, "8-12" for Intermediate, "6-10" for Advanced (NEVER null, ALWAYS a string)
      - weightRange: REQUIRED string - "0" for bodyweight, "10-20" for Beginner, "20-40" for Intermediate, "40-60" for Advanced (NEVER null, ALWAYS a string)
      - type: REQUIRED string - MUST be one of: "Standard", "Dropset", or "Superset" (NEVER null)
      - setsList: Array of set objects
        * Standard: [{{"setType": "Standard", "setNumber": 1, "reps": 12, "weight": 0, "unit": "lbs", "completed": false}}] (repeat for all sets)
        * Dropset: [{{"setType": "Dropset", "setNumber": 1, "subSets": [{{"label": "A", "reps": 12, "weight": 30, "completed": false}}, {{"label": "B", "reps": 10, "weight": 25, "completed": false}}, {{"label": "C", "reps": 8, "weight": 20, "completed": false}}]}}]
        * Superset: [{{"setType": "Superset", "setNumber": 1, "subSets": [{{"label": "A", "reps": 15, "weight": 30, "completed": false}}, {{"label": "B", "reps": 15, "weight": 30, "completed": false}}]}}]

CRITICAL VALIDATION RULES:
- EVERY exercise MUST have ALL fields populated from provided exercises
- NEVER use null for: gif_url, secondary_muscles, target_muscles, repsRange, weightRange, type
- If provided field is null, use empty string "" instead
- repsRange and weightRange MUST ALWAYS be strings (e.g., "12-15", not 12-15 or null)
- type MUST ALWAYS be "Standard", "Dropset", or "Superset" (never null)
- Generate EXACTLY 7 days (Monday-Sunday)
- If previous plan exists, maintain similar body part split on same days unless progression requires changes
- Apply progressive overload: increase weight by 5-10% or reps by 1-2 from previous week
- Each day uses exercises from its corresponding body_part
- Sunday = light recovery workout
- For Standard: include reps, weight, unit, completed fields in each set object
- For Dropset/Superset: ONLY include subSets array (no reps/weight/unit at top level)
- Dropset subSets: 3-4 descending weights with labels A,B,C,D
- Superset subSets: 2 exercises with labels A,B
- weight MUST be integer (0 for bodyweight)
- unit is "lbs" if weight > 0, otherwise null
- completed always false
- Vary exercises and intensity across the week
- Use ONLY exercises provided
- Keep ALL strings short and without escaped quotes or special chars that break JSON

IMPORTANT: Your response MUST be valid JSON.  
- Do NOT include any text, explanation, or formatting outside the JSON object.  
- All keys and string values MUST use double quotes.  
- Do NOT use single quotes, comments, or trailing commas.  
- The JSON MUST be directly parsable by Python's json.loads() without any modification.  
- If you cannot generate the required data, return an empty JSON object: {{}}.

Return ONLY the JSON object."""

    user_prompt = f'Create a comprehensive 7-day workout plan for user {user_id}. Analyze the previous workouts provided, then generate an appropriate progressive workout plan using the available exercises.'

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def generate_plans_for_users_batch(user_ids: List[str]) -> Dict[str, Any]:
    """
    Generate workout plans for multiple users using OpenAI Batch API.
    This bypasses rate limits by submitting all requests asynchronously.
    
    Args:
        user_ids: List of user IDs to process
    
    Returns:
        Dictionary with batch_id, results, and errors
    """
    try:
        print(f"🚀 Starting batch processing for {len(user_ids)} users")
        
        # Step 1: Prepare data for all users
        user_data_list = []
        for user_id in user_ids:
            user_data = prepare_batch_request_data(user_id)
            user_data_list.append(user_data)
        
        # Step 2: Create batch requests (JSONL format)
        batch_requests = []
        for user_data in user_data_list:
            messages = create_batch_prompt(user_data)
            request_id = f"req_{user_data['user_id']}_{uuid.uuid4().hex[:8]}"
            batch_requests.append({
                "custom_id": request_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o",
                    "messages": messages,
                    "max_tokens": 12000,  # INCREASED: From 4000 to 8000 to allow larger outputs
                    "temperature": 0.1  # LOWERED: For more consistent, less creative (error-prone) outputs
                }
            })
        
        # Step 3: Create and upload batch file
        batch_file_name = f"workout_plans_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(batch_file_name, 'w') as f:
            for req in batch_requests:
                f.write(json.dumps(req) + '\n')
        
        # Upload the file
        with open(batch_file_name, 'rb') as f:
            batch_file = client.files.create(
                file=f,
                purpose="batch"
            )
        
        os.remove(batch_file_name)  # Clean up
        
        # Step 4: Create batch job
        batch = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"user_count": str(len(user_ids))}
        )
        
        print(f"📤 Batch submitted with ID: {batch.id}")
        
        # Step 5: Poll for completion (with exponential backoff)
        results = {}
        errors = {}
        
        while batch.status in ["validating", "in_progress"]:
            print(f"⏳ Batch {batch.id} status: {batch.status}. Waiting 30s...")
            time.sleep(30)
            batch = client.batches.retrieve(batch.id)
        
        if batch.status == "completed":
            print("✅ Batch completed! Retrieving results...")
            
            # Retrieve output file (successes only)
            output_file = client.files.retrieve(batch.output_file_id)
            output_content = client.files.content(output_file.id).text
            
            # Parse JSONL results (all should be successes with error: null)
            for line in output_content.strip().split('\n'):
                if line.strip():
                    result = json.loads(line)
                    custom_id = result.get('custom_id')
                    error_val = result.get('error')
                    
                    # FIXED: Only treat non-null errors as failures; null means success
                    if error_val is not None:
                        errors[custom_id] = error_val
                        print(f"❌ Batch error for {custom_id}: {error_val}")
                    else:
                        # Extract content from response
                        response = result['response']['body']['choices'][0]['message']['content']
                        user_id = custom_id.split('_')[1]  # Extract from custom_id
                        results[user_id] = response
                        print(f"✅ Raw response received for user {user_id} (length: {len(response)} chars)")
            
            # NEW: Check for error file if present
            if hasattr(batch, 'error_file_id') and batch.error_file_id:
                print("🔍 Retrieving error file for additional failures...")
                error_file = client.files.retrieve(batch.error_file_id)
                error_content = client.files.content(error_file.id).text
                for line in error_content.strip().split('\n'):
                    if line.strip():
                        err_result = json.loads(line)
                        err_custom_id = err_result.get('custom_id')
                        err_error = err_result.get('error', {})
                        errors[err_custom_id] = err_error.get('message', 'Unknown error')
                        print(f"❌ Error file entry for {err_custom_id}: {err_error}")
        
        elif batch.status == "failed":
            print(f"❌ Batch failed: {batch.errors}")
            return {"success": False, "batch_id": batch.id, "errors": batch.errors}
        
        # Step 6: Process results into plans
        processed_results = {}
        success_count = 0
        for user_id, content in results.items():
            try:
                print(f"🔄 Processing response for user {user_id}...")
                
                # Dump full raw content to file for debugging
                # raw_file = f"raw_response_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                # with open(raw_file, 'w', encoding='utf-8') as f:
                #     f.write(content)
                # print(f"💾 Raw response saved to {raw_file} for inspection")
                
                # Extract JSON (handle ```json wrappers)
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.rfind('```')  # Use rfind to get the last closing ```
                    if json_end == -1:
                        json_end = len(content)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content.strip()
                
                print(f"📄 Extracted JSON string length: {len(json_str)} chars")
                
                weekly_json = json.loads(json_str)
                print(f"✅ JSON parsed: {len(weekly_json.get('weeklyPlan', []))} days found")
                
                validated_plans = []
                
                for i, day_plan in enumerate(weekly_json.get('weeklyPlan', [])):
                    try:
                        validated = WorkoutPlanContainer(workoutPlan=day_plan)
                        validated_dict = validated.model_dump()
                        validated_plans.append(validated_dict)
                        print(f"  ✅ Day {i+1} validated successfully")
                    except Exception as day_e:
                        print(f"  ❌ Day {i+1} validation failed: {str(day_e)}")
                        print(f"  Day plan preview: {json.dumps(day_plan, indent=2)[:500]}...")
                        raise  # Re-raise to fail the user
                
                processed_results[user_id] = {
                    "success": True,
                    "user_id": user_id,
                    "weekly_plan": validated_plans,
                    "token_usage": 0  # Batch doesn't provide per-request tokens; track separately if needed
                }
                
                success_count += 1
                # Store summary
                summary_result = get_summary(processed_results[user_id])
                store_summary_in_pinecone(summary_result)
                print(f"✅ Summary stored for user {user_id}")
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error for user {user_id}: {str(e)}")
                print(f"Raw content preview: {content[:500]}...")
                print(f"Full error context: {e.msg} at line {e.lineno} col {e.colno}")
                processed_results[user_id] = {
                    "success": False,
                    "error": f"Invalid JSON: {str(e)}",
                    "raw_response": content[:1000]
                }
            except Exception as e:
                print(f"❌ Processing error for user {user_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                processed_results[user_id] = {
                    "success": False,
                    "error": f"Processing error: {str(e)}",
                    "raw_response": content[:500]
                }
        
        print(f"🎉 Batch processing complete. Success: {success_count}/{len(user_ids)}")
        
        return {
            "success": success_count > 0,  # Overall success if at least one succeeded
            "batch_id": batch.id,
            "results": processed_results,
            "errors": errors
        }
    
    except Exception as e:
        print(f"❌ Batch processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ==================== LEGACY: SINGLE USER AGENT FUNCTION (FOR TESTING/NON-BATCH) ====================

def get_weekly_ai_response(user_id: str) -> Dict[str, Any]:
    """
    Generate a weekly workout plan using LangChain agent with tool calling.
    The agent will decide whether to check previous plans and create progressive workouts.
    (Use only for single-user testing; prefer batch for multiple users)
    
    Args:
        user_id: User identifier
    
    Returns:
        Dictionary containing the generated weekly plan and metadata
    """
    try:
        # Create tools with user context
        tools = create_database_tools(user_id)
        
        system_prompt = f"""You are a professional fitness trainer AI assistant that creates personalized weekly workout plans.

IMPORTANT: You MUST follow this workflow in order:

STEP 1: CHECK PREVIOUS WORKOUT HISTORY
- ALWAYS call get_previous_workout_summary tool FIRST before creating any plan
- Analyze the previous workout data to understand:
  * Which body parts were trained and on which days
  * Any rest days or recovery patterns
- If previous data exists, create a progressive plan that:
  * Continues from where the previous week ended
  * Increases volume/intensity appropriately (progressive overload)
  * Maintains similar body part split unless user requested changes
  * Varies exercises while keeping similar movement patterns

STEP 2: FETCH AVAILABLE EXERCISES
- Call fetch_exercises_from_database tool to get all available exercises
- CRITICAL: You MUST use the complete exercise data from the database
- DO NOT use exercise data from previous workout summaries as they may be incomplete
- Match exercises to the body parts from previous plan or new requirements

STEP 3: CREATE WORKOUT PLAN
- Design a comprehensive 7-day workout plan based on:
  * Previous workout context (if available) - USE ONLY for understanding progression and body part split
  * User's fitness level
  * Progressive overload principles
  * Exercise variety and balance
- CRITICAL: For EVERY exercise in the plan, you MUST use the COMPLETE data from fetch_exercises_from_database
- NEVER leave any required fields as null or empty


USER INFORMATION:
- User ID: {user_id}

CRITICAL VALIDATION RULES:
- For EVERY day, you MUST include a minimum of 3 and a maximum of 5 exercises.
- If you generate fewer than 3 or more than 5 exercises for any day, you MUST immediately correct the plan before returning.
- NEVER generate fewer than 3 or more than 5 exercises for any day.
- If the database returns fewer than 3 available exercises for a body part, select additional exercises from other relevant body parts to reach at least 3 per day.
- If the database returns more than 5, select only the 5 most relevant exercises for that day.
- You MUST validate the final plan before returning: each day must have between 3 and 5 exercises, no exceptions.

Return JSON with "weeklyPlan" array containing 7 workoutPlan objects:
- weeklyPlan: Array of workout objects
  - workoutPlan: Object containing:
    - id: "wp_" + 8 random digits
    - day: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday
    - title: Descriptive name based on body parts
    - date: {datetime.now().isoformat()}
    - durationMinutes: 30-60 minutes
    - level: Beginner, Intermediate, or Advanced
    - category: Body part from exercises
    - notes: Training tip about form and rest periods
    - exercises: Array of exercise objects (ALL fields REQUIRED - NO null values allowed):
      - id: MUST use exercise_id from fetch_exercises_from_database tool
      - bodyParts: MUST use body_parts from fetch_exercises_from_database tool
      - equipments: MUST use equipment from fetch_exercises_from_database tool
      - instructions: MUST use instructions from fetch_exercises_from_database tool (use empty string "" if null in database)
      - gifUrl: MUST use gif_url from fetch_exercises_from_database tool (use empty string "" if null in database)
      - name: MUST use exact name from fetch_exercises_from_database tool
      - summary: REQUIRED. Brief 1-2 sentence summary of this exercise's role and focus in today's workout.
      - secondaryMuscles: MUST use secondary_muscles from fetch_exercises_from_database tool (use empty string "" if null in database)
      - targetMuscles: MUST use target_muscles from fetch_exercises_from_database tool (use empty string "" if null in database)
      - sets: 2-5 sets based on fitness level (REQUIRED integer)
      - repsRange: REQUIRED string - "12-15" for Beginner, "8-12" for Intermediate, "6-10" for Advanced (NEVER null, ALWAYS a string)
      - weightRange: REQUIRED string - "0" for bodyweight, "10-20" for Beginner, "20-40" for Intermediate, "40-60" for Advanced (NEVER null, ALWAYS a string)
      - type: REQUIRED string - MUST be one of: "Standard", "Dropset", or "Superset" (NEVER null)
      - setsList: Array of set objects
        * Standard: [{{"setType": "Standard", "setNumber": 1, "reps": 12, "weight": 0, "unit": "lbs", "completed": false}}] (repeat for all sets)
        * Dropset: [{{"setType": "Dropset", "setNumber": 1, "subSets": [{{"label": "A", "reps": 12, "weight": 30, "completed": false}}, {{"label": "B", "reps": 10, "weight": 25, "completed": false}}, {{"label": "C", "reps": 8, "weight": 20, "completed": false}}]}}]
        * Superset: [{{"setType": "Superset", "setNumber": 1, "subSets": [{{"label": "A", "reps": 15, "weight": 30, "completed": false}}, {{"label": "B", "reps": 15, "weight": 30, "completed": false}}]}}]

CRITICAL VALIDATION RULES:
- MUST call tools in this order: get_previous_workout_summary → fetch_exercises_from_database → (create plan) 
- EVERY exercise MUST have ALL fields populated from fetch_exercises_from_database
- NEVER use null for: gif_url, secondary_muscles, target_muscles, repsRange, weightRange, type
- If database field is null, use empty string "" instead
- repsRange and weightRange MUST ALWAYS be strings (e.g., "12-15", not 12-15 or null)
- type MUST ALWAYS be "Standard", "Dropset", or "Superset" (never null)
- Generate EXACTLY 7 days (Monday-Sunday)
- If previous plan exists, maintain similar body part split on same days unless progression requires changes
- Apply progressive overload: increase weight by 5-10% or reps by 1-2 from previous week
- Each day uses exercises from its corresponding body_part
- Sunday = light recovery workout
- For Standard: include reps, weight, unit, completed fields in each set object
- For Dropset/Superset: ONLY include subSets array (no reps/weight/unit at top level)
- Dropset subSets: 3-4 descending weights with labels A,B,C,D
- Superset subSets: 2 exercises with labels A,B
- weight MUST be integer (0 for bodyweight)
- unit is "lbs" if weight > 0, otherwise null
- completed always false
- Vary exercises and intensity across the week
- Use ONLY exercises provided for each day
- Keep ALL strings short and without escaped quotes or special chars that break JSON
IMPORTANT: Your response MUST be valid JSON.  
- Do NOT include any text, explanation, or formatting outside the JSON object.  
- All keys and string values MUST use double quotes.  
- Do NOT use single quotes, comments, or trailing commas.  
- The JSON MUST be directly parsable by Python's json.loads() without any modification.  
- If you cannot generate the required data, return an empty JSON object:.
Return ONLY the JSON object."""

        agent = create_agent(
            model='gpt-4o',
            tools=tools,
            system_prompt=system_prompt
        )

        result = agent.invoke({
            'input': f'Create a comprehensive 7-day workout plan for user {user_id}. Check for previous plans first if there is any, then generate an appropriate progressive workout plan.'
        })

        # Extract the content from the messages list
        if isinstance(result, dict) and 'messages' in result:
            messages = result.get('messages', [])
            if not messages:
                return {
                    "success": False,
                    "error": "No messages in result"
                }

            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
        else:
            content = result.get('output') if isinstance(result, dict) else str(result)

        # Extract JSON from content
        if '```json' in content:
            json_start = content.find('```json') + 7
            json_end = content.find('```', json_start)
            json_str = content[json_start:json_end].strip()
        else:
            json_str = content

        try:
            weekly_json = json.loads(json_str)
            validated_plans = []

            for day_plan in weekly_json.get('weeklyPlan', []):
                validated = WorkoutPlanContainer(workoutPlan=day_plan)
                validated_dict = validated.model_dump()
                validated_plans.append(validated_dict)

            # Token usage extraction
            token_usage = {}
            if isinstance(result, dict) and 'messages' in result:
                last_message = result['messages'][-1]
                if hasattr(last_message, 'usage_metadata'):
                    token_usage = last_message.usage_metadata

            response = {
                "success": True,
                "user_id": user_id,
                "weekly_plan": validated_plans,
                "token_usage": token_usage.get('total_tokens', 0) if token_usage else 0
            }
            
            # Store summary
            summary_result = get_summary(response)
            store_summary_in_pinecone(summary_result)
            
            return response
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": "Invalid JSON format",
                "details": str(e),
                "raw_response": content[:1000]
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Validation error",
                "details": str(e),
                "raw_response": content[:1000]
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate workout plan: {str(e)}"
        }


def get_summary(result: Dict):
    try:
        user_id = result.get('user_id')
        weekly_plan = result.get('weekly_plan')
        total_workouts = []
        for item in weekly_plan:
            workout = item.get('workoutPlan', {})
            day = workout.get('day')
            for data in workout.get('exercises', []):
                exercise_id = data.get('id')
                summary = data.get('summary')
                bodyParts = data.get('bodyParts')
                total_workouts.append((day, exercise_id, bodyParts, summary))
        return {
            'user_id': user_id,
            'total_workouts': total_workouts
        }
    except Exception as e:
        return str(e)


def store_summary_in_pinecone(summary_result: Dict):
    """
    Stores each workout summary in Pinecone vector DB with user_id and week date as metadata.
    Generates embeddings for each summary.
    """
    user_id = summary_result.get('user_id')
    total_workouts = summary_result.get('total_workouts', [])
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date().isoformat()
    
    embedding_service.delete_vectors(
        filter={"user_id": user_id, "week_start": week_start},
        namespace="workout_summaries"
    )

    for item in total_workouts:
        if isinstance(item, tuple) and len(item) == 4:
            day, exercise_id, bodyParts, summary = item
            if summary:
                embedding = embedding_service.generate_embedding(summary)
                log_id = f"{user_id}_{week_start}_{day}_{exercise_id}"
                vector_data = [{
                    'id': log_id,
                    'embedding': embedding,
                    'metadata': {
                        "user_id": user_id,
                        "week_start": week_start,
                        "exercise_id": exercise_id,
                        "summary": summary,
                        "day": day,
                        "bodyParts": bodyParts
                    }
                }]
                embedding_service.upsert_vectors(
                    vectors=vector_data,
                    namespace="workout_summaries"
                )
    return "Stored"


# # Example usage in cron job:
# user_ids = ["688b866cccac2136d4304137", "688b86a3ccac2136d430413a","68874f18f57bb89cdb64d391","688759074b7f999ccaaf8042"
#             "688786183cbd70a8513546bf","68878809471dcf0d186cad54","6887c7bf471dcf0d186cad84","6887cedb471dcf0d186cad9c",
#             "6889c947ef389e89715c85bf","688acc2e190ad3fb622ac729"]  # Fetch from DB
# batch_result = generate_plans_for_users_batch(user_ids)
# if batch_result["success"]:
#     for user_id, plan in batch_result["results"].items():
#         if plan["success"]:
#             # Save plan to DB
#             print(f"Saved plan for {user_id}")
#         else:
#             # Handle error
#             print(f"Error for {user_id}: {plan['error']}")