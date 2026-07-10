from fitness_file.exercise_tool import (
    get_weekly_ai_response, 
    get_summary, 
    store_summary_in_pinecone,
    generate_plans_for_users_batch  # Import the batch function
)

from fastapi import Query, Depends, APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from utils import get_user_by_id, validate_session_id
from datetime import datetime
from typing import List
import json
import uuid
import requests

class RequestModel(BaseModel):
    MONGODB_ID: str

class BatchRequestModel(BaseModel):
    user_ids: List[str]  # List of MongoDB user IDs

router = APIRouter()

def run_weekly_plan(user_id_str):
    """Background task for single user weekly plan generation"""
    print("🔄 === BACKGROUND TASK STARTED ===")
    print(f"📋 Task Parameters: user_id_str={user_id_str}")
    
    # Run the AI weekly plan generator
    print("🤖 Calling get_weekly_ai_response...")
    planner = get_weekly_ai_response(user_id=user_id_str)
    print(f"🤖 AI Response received: {planner}")
    print(f"🤖 AI Response type: {type(planner)}")

    # Process week number
    print("📊 Processing week number...")
    week_number = None
    if isinstance(planner, dict):
        week_number = planner.get('week_number') or planner.get('weekNumber')
        print(f"📊 Week number from planner: {week_number}")

    if not week_number:
        week_number = datetime.now().isocalendar()[1]
        print(f"📊 Using current ISO week as fallback: {week_number}")

    # Build payload
    node_payload = {
        "userId": user_id_str,
        "weekNumber": week_number,
        "status": True,
        "Result": {
            "weekly_plan": planner['weekly_plan'] if isinstance(planner, dict) and 'weekly_plan' in planner else planner
        }
    }
    print(f"📦 Node.js payload prepared: {node_payload}")

    print("🌐 Sending POST request to Node.js backend...")
    try:
        response = requests.post(
            "https://fitness-backend.projectco.space/api/v1/cron/save-plan",
            json=node_payload,
            timeout=120
        )
        print(f"🌐 Response status code: {response.status_code}")
        print(f"🌐 Response headers: {dict(response.headers)}")
        response.raise_for_status()
        response_json = response.json()
        print("✅ Plan saved successfully in Node.js:", response_json)
    except requests.exceptions.Timeout as e:
        print(f"⏰ Timeout error saving plan in Node.js: {str(e)}")
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 Connection error saving plan in Node.js: {str(e)}")
    except requests.exceptions.HTTPError as e:
        print(f"🌐 HTTP error saving plan in Node.js: {str(e)}")
        print(f"🌐 Response content: {response.text}")
    except Exception as e:
        print(f"❌ Unexpected error saving plan in Node.js: {str(e)}")

    # Generate and store summary
    print("📝 Generating summary...")
    
    # Check if plan generation was successful before creating summary
    if isinstance(planner, dict) and planner.get('success', False):
        summary_input = {
            'user_id': user_id_str,
            # 'session_id': session_id,
            'weekly_plan': planner['weekly_plan'] if isinstance(planner, dict) and 'weekly_plan' in planner else planner
        }
        print(f"📝 Summary input data: {summary_input}")
        
        summary_result = get_summary(planner)
        print(f"📝 Summary Results: {summary_result}")
        print(f"📝 Summary Results type: {type(summary_result)}")
        
        # Only store in Pinecone if summary was generated successfully
        if summary_result and isinstance(summary_result, dict):
            print("📌 Storing summary in Pinecone...")
            try:
                pinecone_result = store_summary_in_pinecone(summary_result)
                print(f"📌 Pinecone storage result: {pinecone_result}")
            except Exception as e:
                print(f"❌ Error storing in Pinecone: {str(e)}")
        else:
            print("⚠️ Skipping Pinecone storage - no valid summary generated")
    else:
        print(f"⚠️ Skipping summary generation - plan creation failed: {planner.get('error') if isinstance(planner, dict) else 'Unknown error'}")
    
    print("✅ === BACKGROUND TASK COMPLETED ===")


def run_batch_weekly_plans(user_ids: List[str]):
    """Background task for batch weekly plan generation"""
    print("🚀 === BATCH BACKGROUND TASK STARTED ===")
    print(f"📋 Task Parameters: user_ids={user_ids}")
    print(f"👥 Total users to process: {len(user_ids)}")
    
    try:
        # Run the batch AI weekly plan generator
        print("🤖 Calling generate_plans_for_users_batch...")
        batch_result = generate_plans_for_users_batch(user_ids)
        print(f"🤖 Batch Response received")
        print(f"🤖 Batch Status: {batch_result.get('success')}")
        print(f"🤖 Batch ID: {batch_result.get('batch_id')}")
        
        if not batch_result.get('success'):
            print(f"❌ Batch generation failed: {batch_result.get('error')}")
            return
        
        results = batch_result.get('results', {})
        errors = batch_result.get('errors', {})
        
        print(f"✅ Successfully processed {len(results)} users")
        print(f"❌ Failed to process {len(errors)} users")
        print('Batch Results',batch_result)
        
        # Process each successful result
        success_count = 0
        failure_count = 0
        
        for user_id, result in results.items():
            print(f"\n📋 Processing result for user: {user_id}")
            
            if not result.get('success'):
                print(f"❌ User {user_id} failed: {result.get('error')}")
                failure_count += 1
                continue
            
            try:
                # Process week number
                week_number = result.get('week_number') or result.get('weekNumber')
                if not week_number:
                    week_number = datetime.now().isocalendar()[1]
                print(f"📊 Week number for user {user_id}: {week_number}")
                
                # Build payload for Node.js
                node_payload = {
                    "userId": user_id,
                    "weekNumber": week_number,
                    "status": True,
                    "Result": {
                        "weekly_plan": result.get('weekly_plan', [])
                    }
                }
                print(f"📦 Node.js payload prepared for user {user_id}")
                
                # Send to Node.js backend
                print(f"🌐 Sending POST request to Node.js for user {user_id}...")
                response = requests.post(
                    "https://fitness-backend.projectco.space/api/v1/cron/save-plan",
                    json=node_payload,
                    timeout=120
                )
                response.raise_for_status()
                response_json = response.json()
                print(f"✅ Plan saved successfully in Node.js for user {user_id}: {response_json}")
                
                success_count += 1
                
            except requests.exceptions.Timeout as e:
                print(f"⏰ Timeout error for user {user_id}: {str(e)}")
                failure_count += 1
            except requests.exceptions.ConnectionError as e:
                print(f"🔌 Connection error for user {user_id}: {str(e)}")
                failure_count += 1
            except requests.exceptions.HTTPError as e:
                print(f"🌐 HTTP error for user {user_id}: {str(e)}")
                print(f"🌐 Response content: {response.text}")
                failure_count += 1
            except Exception as e:
                print(f"❌ Unexpected error for user {user_id}: {str(e)}")
                failure_count += 1
        
        print(f"\n📊 === BATCH PROCESSING SUMMARY ===")
        print(f"✅ Successfully sent to Node.js: {success_count}/{len(user_ids)}")
        print(f"❌ Failed to send to Node.js: {failure_count}/{len(user_ids)}")
        print(f"📝 Summaries already stored in Pinecone during batch generation")
        print("✅ === BATCH BACKGROUND TASK COMPLETED ===")
        
    except Exception as e:
        print(f"❌ Fatal error in batch background task: {str(e)}")
        import traceback
        traceback.print_exc()


@router.post('/weekly-plan')
async def get_api_weekly_plan_single(
    requests: RequestModel,
    session_id_head: str = Depends(validate_session_id),
    background_tasks: BackgroundTasks = None
):
    """Single user weekly plan generation endpoint"""
    print("🚀 === WEEKLY PLAN API CALLED ===")
    print(f"📥 Incoming Request Data: {requests.dict()}")
    print(f"🔐 Session ID Header: {session_id_head}")
    
    try:
        if not session_id_head:
            print("❌ Invalid Session ID - Raising HTTPException")
            raise HTTPException(status_code=400, detail='Invalid Session ID')

        user_id = requests.MONGODB_ID
        print(f"👤 User ID from request: {user_id}")
        
        user = get_user_by_id(user_id)
        print(f"👤 User data retrieved: {user}")
        
        user_id_str = str(user['_id'])
        print(f"👤 User ID string: {user_id_str}")

        print(f"✅ All validations passed. Starting background task...")
        print(f"📋 Background task parameters: user_id_str={user_id_str}")
        
        # Run the long task in the background
        background_tasks.add_task(run_weekly_plan, user_id_str)

        # Immediately return response to frontend
        response_data = {
            'status': True,
            'message': 'Exercise plan is being generated'
        }
        print(f"📤 Returning response to frontend: {response_data}")
        return response_data

    except Exception as e:
        error_response = {
            'status': False,
            'message': str(e)
        }
        print(f"❌ Exception occurred: {str(e)}")
        print(f"📤 Returning error response: {error_response}")
        return error_response


@router.post('/weekly-plan-batch')
async def get_api_weekly_plan_batch(
    requests: BatchRequestModel,
    session_id_head: str = Depends(validate_session_id),
    background_tasks: BackgroundTasks = None
):
    """Batch weekly plan generation endpoint for multiple users"""
    print("🚀 === BATCH WEEKLY PLAN API CALLED ===")
    print(f"📥 Incoming Request Data: {requests.dict()}")
    print(f"🔐 Session ID Header: {session_id_head}")
    print(f"👥 Number of users: {len(requests.user_ids)}")
    
    try:
        if not session_id_head:
            print("❌ Invalid Session ID - Raising HTTPException")
            raise HTTPException(status_code=400, detail='Invalid Session ID')

        if not requests.user_ids or len(requests.user_ids) == 0:
            print("❌ No user IDs provided - Raising HTTPException")
            raise HTTPException(status_code=400, detail='At least one user ID is required')

        # Validate all user IDs exist
        print("👤 Validating user IDs...")
        validated_user_ids = []
        for user_id in requests.user_ids:
            try:
                user = get_user_by_id(user_id)
                user_id_str = str(user['_id'])
                validated_user_ids.append(user_id_str)
                print(f"✅ User validated: {user_id_str}")
            except Exception as e:
                print(f"⚠️ Invalid user ID {user_id}: {str(e)}")
                # Continue with other valid users
                continue
        
        if not validated_user_ids:
            print("❌ No valid user IDs found - Raising HTTPException")
            raise HTTPException(status_code=400, detail='No valid user IDs provided')

        print(f"✅ All validations passed. Starting batch background task...")
        print(f"📋 Background task parameters: {len(validated_user_ids)} users")
        
        # Run the batch task in the background
        background_tasks.add_task(run_batch_weekly_plans, validated_user_ids)

        # Immediately return response to frontend
        response_data = {
            'status': True,
            'message': f'Batch exercise plans are being generated for {len(validated_user_ids)} users',
            'user_count': len(validated_user_ids),
            'valid_users': len(validated_user_ids),
            'invalid_users': len(requests.user_ids) - len(validated_user_ids)
        }
        print(f"📤 Returning response to frontend: {response_data}")
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        error_response = {
            'status': False,
            'message': str(e)
        }
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"📤 Returning error response: {error_response}")
        return error_response