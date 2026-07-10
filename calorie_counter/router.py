from calorie_counter.coach import*
from fastapi import APIRouter,HTTPException,status,Header,Depends
from fastapi.responses import JSONResponse
import os
from utils import get_user_by_id


router=APIRouter()

VALID_SESSION_ID = os.getenv("SESSION_ID")

def validate_session_id(session_id: str = Header(..., alias="Session-Id")):
    if session_id != VALID_SESSION_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session ID"
        )
    return session_id 



@router.post('/calorie-counter')

def calorie_counter(user_id, session_id=Depends(validate_session_id)):
    try:
        if not session_id:
            return HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Incorrect Session ID')
        
        user_details=get_user_by_id(user_id)
        if not user_details:
            return HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='User not found')
        
        print('User ID',user_details['_id'])

        results=ai_coach(str(user_details['_id']))
        print('Result',results)

        return JSONResponse({
            'message':'success',
            'status':True,
            'content':results
        })
    except Exception as e:
        return JSONResponse({
            'message':'Failed',
            'status':False,
            'error':str(e)
        })



