from fastapi import APIRouter,HTTPException, Header, status
from chatbot.coach import FitnessCoach
from pydantic import BaseModel
import json
from typing import Optional
import uuid
from fastapi import Query
from fastapi.responses import JSONResponse
from fastapi import Depends
from utils import get_user_by_id
import os
import uuid


router=APIRouter()

class ChatRequest(BaseModel):
    message:str
    MONGODB_ID:str
    session_id:str

VALID_SESSION_ID = os.getenv("SESSION_ID")

def validate_session_id(session_id: str = Header(..., alias="Session-Id")):
    if session_id != VALID_SESSION_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session ID"
        )
    return session_id    

@router.post('/ai-coach')
def ai_coach(chatrequest: ChatRequest,
            header_session_id: str = Depends(validate_session_id)
):
    try:
        # Use provided session_id or generate a new one
        if not header_session_id:
            return HTTPException(status_code=400,detail='Invalid Session')

        message = chatrequest.message

        if not chatrequest.session_id:
            return HTTPException(status_code=400,detail='Session ID required')

        user_id=chatrequest.MONGODB_ID

        if not user_id:
            return  JSONResponse(content={
                    'status':False,
                    'error':'user not logged in'
                })
        
        user=get_user_by_id(user_id)
        if user is None:
            return HTTPException(status_code=400,detail='Invalid user')
        

        if not message:
            raise HTTPException(status_code=400, detail='Failed: no message provided')


        print('User',user)

        # Pass session_id to FitnessCoach
        coach = FitnessCoach(session_id=chatrequest.session_id,user_id=user['_id'])

        result = coach.chat(message)

        return {
            'status': True,
            'result': result,
            'user email':user['email'],
            'session_id': chatrequest.session_id  # Always return the session_id for client reuse
        }
    except Exception as e:
        return {
            'status': False,
            'error': str(e)
        }
    

# @router.get('/ai-coach/history')
# def get_coach_history(
#     session_id: str,
#     mongodb_id:str,
#     page: int = Query(1, ge=1),
#     page_size: int = Query(10, ge=1, le=100)
    

# ):
#     try:
#         user=get_user_by_id(mongodb_id)
#         coach = FitnessCoach(session_id=session_id,user_id=user)
#         result = coach.get_paginated_history(page=page, page_size=page_size)
#         return {
#             "status": True,
#             "result": result,
#             'name':user['fullName']
#         }
#     except Exception as e:
#         return {
#             "status": False,
#             "error": str(e)
#         }




@router.get('/ai-coach/history')
def get_coach_history(
    session_id:str,
    session_id_head: str =Depends(validate_session_id),
    mongodb_id: str=Query(...,alias='mongodb_id'),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    
):
    try:
        user = get_user_by_id(mongodb_id)
        
        if not user:
            return {
                "status": False,
                "error": "User not found"
            }
        
        if not session_id_head:
            HTTPException(status_code=400,detail='Invalid header Session ID')
        

        if not session_id:
            HTTPException(status_code=400,detail='Invalid Session ID')

        coach = FitnessCoach(session_id=session_id, user_id=str(user['_id']))
        result = coach.get_paginated_history_from_db(page=page, page_size=page_size)
        
        return {
            "status": True,
            "result": result,
            "name": user.get('fullName', 'Unknown')
        }
    except Exception as e:
        return {
            "status": False,
            "error": str(e)
        }
    

@router.post('/new-chat')
def new_chat(user_id):
    user=get_user_by_id(user_id)
    if user:
        return str(uuid.uuid4())
    else:
        return ('No user found')