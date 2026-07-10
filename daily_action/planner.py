from dotenv import load_dotenv
import os
from openai import OpenAI
from datetime import datetime, timedelta, timezone
from langchain.agents import create_agent
from daily_action.tools import create_health_data_tools
from typing import List
import uuid
import json
import time

load_dotenv()

OPENAI_API_KEY=os.getenv('OPENAI_API_KEY')

client=OpenAI(api_key=OPENAI_API_KEY)


def get_system_prompt():
    return """
You are a plan generator that returns health action plans.

INSTRUCTIONS:
1. Use tools to check user's health data from last 2 days
2. Generate 3-5 actions based on their needs
3. Return ONLY raw JSON - no text before or after

RULES:
- NO greetings, NO explanations, NO context
- NO "based on your data", NO "here's your plan"  
- NO morning/evening/midnight categorization
- NO descriptions or details beyond the title
- NO markdown code blocks (```json)
- Response must be ONLY the JSON object
- First character must be {
- Last character must be }

REQUIRED FORMAT:
{
  "actions": [
    {"title": "Go for a 30-minute brisk walk"},
    {"title": "Drink 8 glasses of water throughout the day"},
    {"title": "Practice deep breathing for 10 minutes"}
  ]
}

Examples of GOOD titles:
- "Take a 20-minute walk outside"
- "Eat a protein-rich breakfast"
- "Log your meals in the food tracker"
- "Stretch for 10 minutes before bed"
- "Drink water with every meal"

Examples of BAD titles (DO NOT USE):
- "Morning: Start your day with..." ❌
- "Hydration - Drink water throughout..." ❌
- "Go for a walk (this will help boost your energy)" ❌

Return ONLY the JSON. Start typing { now.
"""

def daily_action(user_id):
    if not user_id:
        return {
            'status': False,
            'message': 'No user found'
        }

    # Get all tools
    tools = create_health_data_tools(user_id)
    system_prompt = get_system_prompt()


    # Instead of collecting user_data and passing it in the prompt, do:
# ...existing code...
    agent = create_agent(
        model="gpt-4o",
        tools=tools,
        system_prompt=system_prompt
    )    

    response = agent.invoke({
    "input": '{"actions":[{"title":"..."}]} - Return this format only. No text.'
})    
    messages = response.get('messages', [])
    if not messages:
        return {'status': False, 'message': 'No response from AI'}
    
    last_message = messages[-1]
    content = last_message.content

    return content

def create_batch_user(user_ids: List[str]):
    try:
        print(f"🚀 Starting batch processing for {len(user_ids)} users")

        # Generate daily action plan for each user
        user_plans = {}
        for user_id in user_ids:
            plan = daily_action(user_id)
            user_plans[user_id] = plan

        # If you want to use these plans in your batch requests, you can include them in the batch_requests
        batch_requests = []
        for user_id in user_ids:
            plan = user_plans[user_id]
            request_id = f"req_{user_id}_{uuid.uuid4().hex[:8]}"
            batch_requests.append({
                "custom_id": request_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": get_system_prompt()},
                        # You can include the generated plan as context for the user message if needed
                        {"role": "user", "content": f"User's daily plan: {plan}"}
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.5
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
            return {
                "success": True,
                "batch_id": batch.id,
                "results": results,
                "errors": errors
            }
        
        elif batch.status == "failed":
            print(f"❌ Batch failed: {batch.errors}")
            return {"success": False, "batch_id": batch.id, "errors": batch.errors}
        return {
            "success": False,
            "error": f"Batch ended in unexpected state: {batch.status if 'batch' in locals() else 'unknown'}"
        }
    except Exception as e:
        print(f"❌ Batch processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}