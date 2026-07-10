from fitness_file.embedding_service import EmbeddingService
from dotenv import load_dotenv
import os
from pymongo import MongoClient

from bson import ObjectId
from fastapi import FastAPI,HTTPException, Header, status


load_dotenv()


embedding_service=EmbeddingService()



db_client= MongoClient(os.getenv('MONGODB_URI'))
# Fetch user by MongoDB ObjectId
def get_user_by_id(user_id):
	db = db_client['fitnessApp']
	users = db['users']
	try:
		user = users.find_one({'_id': ObjectId(user_id)})
		return user
	except Exception as e:
		print(f"Error fetching user by id: {e}")
		return 



# print(get_user_by_id('6946c61a2c87c319dafe8835'))


VALID_SESSION_ID = os.getenv("SESSION_ID")

def validate_session_id(session_id: str = Header(..., alias="Session-Id")):
    if session_id != VALID_SESSION_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session ID"
        )
    return session_id  



