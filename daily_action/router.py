# from daily_action.planner import daily_action
# from fastapi import APIRouter,HTTPException,status,Header,Depends
# from utils import get_user_by_id
# from fastapi.responses import JSONResponse
# from typing import List
# router=APIRouter()
# import os


# VALID_SESSION_ID = os.getenv("SESSION_ID")

# def validate_session_id(session_id: str = Header(..., alias="Session-Id")):
#     if session_id != VALID_SESSION_ID:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid session ID"
#         )
#     return session_id    


# @router.post('/daily-actions')
# def end_point(user_id:List[str],session_id_header=Depends(validate_session_id)):
#     try:
#         if not session_id_header:
#             return HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Invalid Session')

#         current_user_id=get_user_by_id(user_id)
#         print('Current user',current_user_id)

#         if not current_user_id:
#             return HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Invalid User')

#         response=daily_action(str(current_user_id))

#         return JSONResponse({
#             'status':True,
#             'message':response,
            
#         })
#     except Exception as e:
#         return JSONResponse({
#             'status':False,
#             'error':str(e)
#         })









from daily_action.planner import create_batch_user
from fastapi import APIRouter, HTTPException, status, Header, Depends, Body
from utils import get_user_by_id
from fastapi.responses import JSONResponse
from typing import List
import os

router = APIRouter()

VALID_SESSION_ID = os.getenv("SESSION_ID")

def validate_session_id(session_id: str = Header(..., alias="Session-Id")):
    if session_id != VALID_SESSION_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session ID"
        )
    return session_id    

@router.post('/daily-actions')
def batch_daily_actions(
    user_ids: List[str] = Body(..., embed=True),
    session_id_header=Depends(validate_session_id)
):
    try:
        if not session_id_header:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'status': False, 'error': 'Invalid Session'}
            )

        # Validate all user IDs
        invalid_ids = []
        valid_ids = []
        for uid in user_ids:
            user_id=get_user_by_id(uid)
            if user_id:
                valid_ids.append(user_id['_id'])
            else:
                invalid_ids.append(uid)

        if invalid_ids:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'status': False,
                    'error': f'Invalid user IDs: {invalid_ids}'
                }
            )

        response = create_batch_user(valid_ids)
        return JSONResponse({
            'status': response.get("success", False),
            'data': response
        })
    except Exception as e:
        return JSONResponse({
            'status': False,
            'error': str(e)
        })