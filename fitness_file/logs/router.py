from fastapi import APIRouter,HTTPException
from fitness_file.logs.log_schema import *
from fitness_file.embedding_service import EmbeddingService
from datetime import datetime,timezone
from utils import embedding_service
from fastapi import UploadFile, File, Form
import os
from typing import Union,Optional

router=APIRouter()
# embedding_service=EmbeddingService()


import sys
import importlib
if 'fitness_file.logs.log_schema' in sys.modules:
    importlib.reload(sys.modules['fitness_file.logs.log_schema'])

def is_log_empty(log_obj, exclude_fields=["timestamp", "MONGODB_user"]):
    for field, value in log_obj.dict().items():
        if field in exclude_fields:
            continue
        if value not in [None, "", 0, [], {}]:
            return False
    return True


@router.post('/water-log')
def get_waterlog(request:WaterLog):
    try:
        if is_log_empty(request):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        text_data=f'water intake {request.quantity} {request.unit}'

        embedding=embedding_service.generate_embedding(text_data)
        if embedding is None:
                raise HTTPException(status_code=400, detail="Failed to generate embedding")

        log_id = f"water_{datetime.now().strftime('%Y%m%d%H%M%S')}"


        vector_data=[{
              'id':log_id,
              'embedding':embedding,
              'metadata':{
                    'type':'water_log',
                    'unit':request.unit,
                    'quantity':request.quantity,
                    'MONGODB_user':request.MONGODB_user,
                    'timestamp':request.timestamp or datetime.now(timezone.utc).isoformat()
              }
        }]

        embedding_service.upsert_vectors(vector_data,namespace='water_log')

        return {
                'status': True,
                'message': 'Water log stored successfully',
                'log_id': log_id
            }
    except Exception as e:
         return {
              'status':False,
              'error':str(e)
         }
     

@router.post('/meal-log')
async def get_meal_log(
    meal_name: str = Form(..., description="Name of the meal"),
    time: Optional[str] = Form(None, description="Time of the meal"),
    calories: float = Form(..., description="Calories in the meal"),
    protein: float = Form(..., description="Protein content in grams"),
    fats: float = Form(..., description="Fat content in grams"),
    carbs: float = Form(..., description="Carbohydrate content in grams"),
    ratings: Optional[float] = Form(None, description="Rating for the meal (1-5)"),
    notes: Optional[str] = Form(None, description="Additional notes about the meal"),
    MONGODB_user: str = Form(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011"),
    timestamp: Optional[str] = Form(None, description="ISO format timestamp (optional, defaults to current time)"),
    photo: Optional[Union[UploadFile,str]] = File(None, description="Optional photo upload")  # Optional photo upload
):
    # Log incoming request data
    print("Meal Log Request Data:", {
        "meal_name": meal_name,
        "time": time,
        "calories": calories,
        "protein": protein,
        "fats": fats,
        "carbs": carbs,
        "ratings": ratings,
        "notes": notes,
        "MONGODB_user": MONGODB_user,
        "timestamp": timestamp,
        "photo": photo.filename if isinstance(photo, UploadFile) else photo
    })
    try:
        if all([
        not meal_name,
        not time,
        calories == 0,
        protein == 0,
        fats == 0,
        carbs == 0,
        not ratings,
        not notes,
        not photo
        ]):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
}
        photo_url = None
        if photo:
            if isinstance(photo, UploadFile):
                os.makedirs("static/meal_photos", exist_ok=True)
                file_location = f"static/meal_photos/{photo.filename}"
                with open(file_location, "wb") as f:
                    f.write(await photo.read())
                photo_url = f"/{file_location}"
            elif isinstance(photo, str):
                # If photo is a URL string, use it directly
                photo_url = photo
       

        text_data = f"""Meal Name {meal_name}, Time {time}, 
        Calories {calories}, Protein {protein}, Fats {fats}, Carbs {carbs}"""

        if notes:
            text_data += f", Notes {notes}"
        # if photo_url:
        #     text_data+= f" Photo {photo_url}"
        # if ratings:
        #     text_data+= f"Ratings {ratings}"

        embeddings = embedding_service.generate_embedding(text_data)
        if embeddings is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")

        log_id = f"meal_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        metadata = {
            'type': 'meal_log',
            'mealname': meal_name,
            'calories': calories,
            'protein': protein,
            'carbs': carbs,
            'MONGODB_user': MONGODB_user,
            'timestamp': timestamp or datetime.now(timezone.utc).isoformat()}
        if time:
            metadata['time'] = time
        if photo_url is not None:
            metadata['photo'] = photo_url
        if notes:
            metadata['notes'] = notes
        if ratings:
            metadata['ratings'] = ratings

        vector_data = [{
            'id': log_id,
            'embedding': embeddings,
            'metadata': metadata
        }]

        embedding_service.upsert_vectors(vector_data, namespace='meal_log')

        return {
            'status': True,
            'Message': 'Meal embeddings stored successfully',
            'log_id': log_id,
            'photo_url': photo_url
        }
    except Exception as e:
        return {
            'status': False,
            'error': str(e)
        }

@router.post('/mood-log')
def log_mood(mood_log: MoodLog):
    """Store mood log with embeddings in Pinecone"""
    try:
        if is_log_empty(mood_log):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        # Create text representation for embedding
        text_data = f"Mood: {mood_log.mood_level}"
        if mood_log.notes:
            text_data+= f" Notes{mood_log.notes}"

        
        # Generate embedding
        embedding = embedding_service.generate_embedding(text_data)
        
        if embedding is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")
        
        # Create unique ID
        log_id = f"mood_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        metadata={
            'mood_level':mood_log.mood_level,
            'MONGODB_user':mood_log.MONGODB_user
        }

        if mood_log.notes:
            metadata['notes']=mood_log.notes

        # Prepare vector for upsert
        metadata['timestamp'] = mood_log.timestamp or datetime.now(timezone.utc).isoformat()
        vector_data = [{
            'id': log_id,
            'embedding': embedding,
            'metadata': metadata
        }]
        
        # Store in Pinecone with namespace 'mood_logs'
        embedding_service.upsert_vectors(vector_data, namespace='mood_logs')
        
        return {
            'status': True,
            'message': 'Mood log stored successfully',
            'log_id': log_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/weight-log')
def log_weight(weight_log: WeightLog):
    """Store weight log with embeddings in Pinecone"""
    try:
        if is_log_empty(weight_log):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        # Create text representation for embedding
        text_data = f"Weight: {weight_log.quantity} {weight_log.units}"
        if weight_log.notes:
            text_data+= f"Notes {weight_log.notes}"
        
        # Generate embedding
        embedding = embedding_service.generate_embedding(text_data)
        
        if embedding is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")
        
        # Create unique ID
        log_id = f"weight_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Prepare vector for upsert
        metadata={
            'type':'weight_log',
            'quantity':weight_log.quantity,
            'units':weight_log.units,
            'MONGODB_user':weight_log.MONGODB_user,
            'timestamp':weight_log.timestamp or datetime.now(timezone.utc).isoformat()
        }
        if weight_log.notes:
            metadata['notes']=weight_log.notes

        vector_data=[{
            'id':log_id,
            'embedding':embedding,
            'metadata':metadata
        }]
        
        # Store in Pinecone with namespace 'weight_logs'
        embedding_service.upsert_vectors(vector_data, namespace='weight_logs')
        
        return {
            'status': True,
            'message': 'Weight log stored successfully',
            'log_id': log_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    
@router.post('/health-fields')
def get_health_fields(request: HealthMetricsLog):
    try:
        if is_log_empty(request):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        
        # Build text data with resolved primitive values
        text_data = f"""Sleep {request.sleep}, Dyration {request.hydration},Body Weight{request.body_weight}, Heart Rate {request.heart_rate}, Steps {request.steps}
        Workouts {request.workouts}, Calories Burned {request.calories_burned}"""

        embeddings = embedding_service.generate_embedding(text_data)

        if embeddings is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")

        # Create unique ID
        log_id = f"health_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Prepare metadata with primitive values only
        metadata = {
            'type': 'health_metrics',
            'sleep': request.sleep,
            'heart_rate': request.heart_rate,
            'steps': request.steps,
            'workouts': request.workouts,
            'hydration':request.hydration,
            'body_weight':request.body_weight,
            'calories_burned': request.calories_burned,
            'MONGODB_user': request.MONGODB_user,
            'timestamp': request.timestamp or datetime.now(timezone.utc).isoformat()
        }
            
        # Store in Pinecone
        vector_data = [{
            'id': log_id,
            'embedding': embeddings,
            'metadata': metadata
        }]
        
        embedding_service.upsert_vectors(vector_data, namespace='health_metrics')
        
        return {
            'status': True,
            'message': 'Health metrics stored successfully',
            'log_id': log_id,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        

@router.post('/sleep-log')
def log_sleep(sleep_log: Sleep):
    """Store sleep log with embeddings in Pinecone"""
    try:
        if is_log_empty(sleep_log):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        text_data = f"Sleep: {sleep_log.sleep} hours"
        if sleep_log.notes:
            text_data += f" Notes: {sleep_log.notes}"

        embedding = embedding_service.generate_embedding(text_data)
        if embedding is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")

        log_id = f"sleep_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        metadata = {
            'type': 'sleep_log',
            'sleep': sleep_log.sleep,
            'user_id':sleep_log.MONGODB_user,
            'timestamp':datetime.now().isoformat()
        }
        if sleep_log.notes:
            metadata['notes'] = sleep_log.notes

        vector_data = [{
            'id': log_id,
            'embedding': embedding,
            'metadata': metadata,
        }]
        embedding_service.upsert_vectors(vector_data, namespace='sleep_log')

        return {
            'status': True,
            'message': 'Sleep log stored successfully',
            'log_id': log_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/pain-log')
def log_pain(pain_log: Pain):
    """Store pain log with embeddings in Pinecone"""
    try:
        if is_log_empty(pain_log):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        
        text_data = f"Pain Level: {pain_log.pain_level}"
        if pain_log.notes:
            text_data += f" Notes: {pain_log.notes}"

        embedding = embedding_service.generate_embedding(text_data)
        if embedding is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")

        log_id = f"pain_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        metadata = {
            'type': 'pain_log',
            'pain_level': pain_log.pain_level,
            'user_id':pain_log.MONGODB_user,
            'timestamp': datetime.now().isoformat()
        }
        if pain_log.notes:
            metadata['notes'] = pain_log.notes

        vector_data = [{
            'id': log_id,
            'embedding': embedding,
            'metadata': metadata
        }]
        embedding_service.upsert_vectors(vector_data, namespace='pain_log')

        return {
            'status': True,
            'message': 'Pain log stored successfully',
            'log_id': log_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/medication-log')
def log_medication(medication: Medication):
    """Store medication log with embeddings in Pinecone"""
    print("Medication Log Request Data:", medication.dict())
    print("Schema fields:", list(medication.__fields__.keys()))  # Th

    try:
        if is_log_empty(medication):
            return {
                'status': False,
                'message': 'Fields should not be zero or null.'
            }
        
        # Build comprehensive text for embedding
        text_data = (
            f"Medicine Name: {medication.name}, Dose: {medication.dose} {medication.unit}, "
            f"Schedule Type: {medication.scheduleType}"
        )
        
        if medication.intervalDays:
            text_data += f", Interval: {medication.intervalDays} days"
        
        if medication.timesOfDay:
            text_data += f", Times of Day: {', '.join(medication.timesOfDay)}"
        
        if medication.customTimes:
            text_data += f", Custom Times: {', '.join(medication.customTimes)}"
        
        if medication.notes:
            text_data += f", Notes: {medication.notes}"

        embedding = embedding_service.generate_embedding(text_data)
        if embedding is None:
            raise HTTPException(status_code=400, detail="Failed to generate embedding")

        log_id = f"medication_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Build complete metadata with all fields
        metadata = {
            'type': 'medication_log',
            'name': medication.name,
            'dose': medication.dose,
            'unit': medication.unit,
            'scheduleType': medication.scheduleType,
            'isActive': medication.isActive,
            'isPriority': medication.isPriority,
            'isTaken': medication.isTaken,
            'takenToday': medication.takenToday,
            'MONGODB_user': medication.MONGODB_user,
            'timestamp': medication.timestamp or datetime.now(timezone.utc).isoformat()
        }
        
        # Add optional fields if present
        if medication.intervalDays:
            metadata['intervalDays'] = medication.intervalDays
        
        if medication.timesOfDay:
            metadata['timesOfDay'] = medication.timesOfDay
        
        if medication.customTimes:
            metadata['customTimes'] = medication.customTimes
        
        if medication.notes:
            metadata['notes'] = medication.notes
        
        if medication.lastTakenDate:
            metadata['lastTakenDate'] = medication.lastTakenDate
        
        if medication.nextScheduledDate:
            metadata['nextScheduledDate'] = medication.nextScheduledDate
        
        if medication.intervalStartDate:
            metadata['intervalStartDate'] = medication.intervalStartDate

        vector_data = [{
            'id': log_id,
            'embedding': embedding,
            'metadata': metadata
        }]
        embedding_service.upsert_vectors(vector_data, namespace='medication_log')

        return {
            'status': True,
            'message': 'Medication log stored successfully',
            'log_id': log_id,
            'medication_data': {
                'name': medication.name,
                'dose': medication.dose,
                'unit': medication.unit,
                'scheduleType': medication.scheduleType,
                'isActive': medication.isActive
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


























# from fastapi import APIRouter, HTTPException
# from fitness_file.logs.log_schema import *
# from fitness_file.embedding_service import EmbeddingService
# from datetime import datetime, timezone
# from utils import embedding_service
# from fastapi import UploadFile, File, Form
# import os
# from typing import Union, Optional

# router = APIRouter()

# import sys
# import importlib
# if 'fitness_file.logs.log_schema' in sys.modules:
#     importlib.reload(sys.modules['fitness_file.logs.log_schema'])


# def is_log_empty(log_obj, exclude_fields=["timestamp", "MONGODB_user"]):
#     for field, value in log_obj.dict().items():
#         if field in exclude_fields:
#             continue
#         if value not in [None, "", 0, [], {}]:
#             return False
#     return True


# def resolve_timestamp(client_timestamp: Optional[str]) -> str:
#     """
#     Always use the client-provided timestamp.
#     Normalizes to UTC ISO 8601 string.
#     Raises ValueError if timestamp is missing or invalid.
#     """
#     if not client_timestamp or not str(client_timestamp).strip():
#         raise ValueError("timestamp is required and must be a valid ISO 8601 datetime string.")
#     try:
#         dt = datetime.fromisoformat(str(client_timestamp).replace('Z', '+00:00'))
#         return dt.astimezone(timezone.utc).isoformat()
#     except (ValueError, TypeError):
#         raise ValueError(f"Invalid timestamp format: '{client_timestamp}'. Expected ISO 8601 (e.g. '2026-04-21T20:00:00+05:30').")


# @router.post('/water-log')
# def get_waterlog(request: WaterLog):
#     try:
#         if is_log_empty(request):
#             return {
#                 'status': False,
#                 'message': 'Fields should not be zero or null.'
#             }

#         timestamp = resolve_timestamp(request.timestamp)

#         text_data = f'water intake {request.quantity} {request.unit}'
#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"water_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

#         vector_data = [{
#             'id': log_id,
#             'embedding': embedding,
#             'metadata': {
#                 'type': 'water_log',
#                 'unit': request.unit,
#                 'quantity': request.quantity,
#                 'MONGODB_user': request.MONGODB_user,
#                 'timestamp': timestamp
#             }
#         }]

#         embedding_service.upsert_vectors(vector_data, namespace='water_log')

#         return {
#             'status': True,
#             'message': 'Water log stored successfully',
#             'log_id': log_id
#         }
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         return {'status': False, 'error': str(e)}


# @router.post('/meal-log')
# async def get_meal_log(
#     meal_name: str = Form(..., description="Name of the meal"),
#     time: Optional[str] = Form(None, description="Time of the meal"),
#     calories: float = Form(..., description="Calories in the meal"),
#     protein: float = Form(..., description="Protein content in grams"),
#     fats: float = Form(..., description="Fat content in grams"),
#     carbs: float = Form(..., description="Carbohydrate content in grams"),
#     ratings: Optional[float] = Form(None, description="Rating for the meal (1-5)"),
#     notes: Optional[str] = Form(None, description="Additional notes about the meal"),
#     MONGODB_user: str = Form(..., description="MongoDB user ID"),
#     timestamp: str = Form(..., description="ISO 8601 timestamp from client device"),  # now required
#     photo: Optional[Union[UploadFile, str]] = File(None, description="Optional photo upload")
# ):
#     print("Meal Log Request Data:", {
#         "meal_name": meal_name, "time": time, "calories": calories,
#         "protein": protein, "fats": fats, "carbs": carbs,
#         "ratings": ratings, "notes": notes, "MONGODB_user": MONGODB_user,
#         "timestamp": timestamp,
#         "photo": photo.filename if isinstance(photo, UploadFile) else photo
#     })
#     try:
#         if all([
#             not meal_name, not time,
#             calories == 0, protein == 0, fats == 0, carbs == 0,
#             not ratings, not notes, not photo
#         ]):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(timestamp)

#         photo_url = None
#         if photo:
#             if isinstance(photo, UploadFile):
#                 os.makedirs("static/meal_photos", exist_ok=True)
#                 file_location = f"static/meal_photos/{photo.filename}"
#                 with open(file_location, "wb") as f:
#                     f.write(await photo.read())
#                 photo_url = f"/{file_location}"
#             elif isinstance(photo, str):
#                 photo_url = photo

#         text_data = f"Meal Name {meal_name}, Time {time}, Calories {calories}, Protein {protein}, Fats {fats}, Carbs {carbs}"
#         if notes:
#             text_data += f", Notes {notes}"

#         embeddings = embedding_service.generate_embedding(text_data)
#         if embeddings is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"meal_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'meal_log',
#             'mealname': meal_name,
#             'calories': calories,
#             'protein': protein,
#             'carbs': carbs,
#             'MONGODB_user': MONGODB_user,
#             'timestamp': timestamp
#         }
#         if time:
#             metadata['time'] = time
#         if photo_url is not None:
#             metadata['photo'] = photo_url
#         if notes:
#             metadata['notes'] = notes
#         if ratings:
#             metadata['ratings'] = ratings

#         vector_data = [{'id': log_id, 'embedding': embeddings, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='meal_log')

#         return {
#             'status': True,
#             'Message': 'Meal embeddings stored successfully',
#             'log_id': log_id,
#             'photo_url': photo_url
#         }
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         return {'status': False, 'error': str(e)}


# @router.post('/mood-log')
# def log_mood(mood_log: MoodLog):
#     """Store mood log with embeddings in Pinecone"""
#     try:
#         if is_log_empty(mood_log):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(mood_log.timestamp)

#         text_data = f"Mood: {mood_log.mood_level}"
#         if mood_log.notes:
#             text_data += f" Notes {mood_log.notes}"

#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"mood_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'mood_level': mood_log.mood_level,
#             'MONGODB_user': mood_log.MONGODB_user,
#             'timestamp': timestamp
#         }
#         if mood_log.notes:
#             metadata['notes'] = mood_log.notes

#         vector_data = [{'id': log_id, 'embedding': embedding, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='mood_logs')

#         return {'status': True, 'message': 'Mood log stored successfully', 'log_id': log_id}
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post('/weight-log')
# def log_weight(weight_log: WeightLog):
#     """Store weight log with embeddings in Pinecone"""
#     try:
#         if is_log_empty(weight_log):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(weight_log.timestamp)

#         text_data = f"Weight: {weight_log.quantity} {weight_log.units}"
#         if weight_log.notes:
#             text_data += f" Notes {weight_log.notes}"

#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"weight_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'weight_log',
#             'quantity': weight_log.quantity,
#             'units': weight_log.units,
#             'MONGODB_user': weight_log.MONGODB_user,
#             'timestamp': timestamp
#         }
#         if weight_log.notes:
#             metadata['notes'] = weight_log.notes

#         vector_data = [{'id': log_id, 'embedding': embedding, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='weight_logs')

#         return {'status': True, 'message': 'Weight log stored successfully', 'log_id': log_id}
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post('/health-fields')
# def get_health_fields(request: HealthMetricsLog):
#     try:
#         if is_log_empty(request):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(request.timestamp)

#         text_data = f"""Sleep {request.sleep}, Hydration {request.hydration}, Body Weight {request.body_weight},
#         Heart Rate {request.heart_rate}, Steps {request.steps},
#         Workouts {request.workouts}, Calories Burned {request.calories_burned}"""

#         embeddings = embedding_service.generate_embedding(text_data)
#         if embeddings is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"health_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'health_metrics',
#             'sleep': request.sleep,
#             'heart_rate': request.heart_rate,
#             'steps': request.steps,
#             'workouts': request.workouts,
#             'hydration': request.hydration,
#             'body_weight': request.body_weight,
#             'calories_burned': request.calories_burned,
#             'MONGODB_user': request.MONGODB_user,
#             'timestamp': timestamp
#         }

#         vector_data = [{'id': log_id, 'embedding': embeddings, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='health_metrics')

#         return {'status': True, 'message': 'Health metrics stored successfully', 'log_id': log_id}
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post('/sleep-log')
# def log_sleep(sleep_log: Sleep):
#     """Store sleep log with embeddings in Pinecone"""
#     try:
#         if is_log_empty(sleep_log):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(sleep_log.timestamp)  # was: datetime.now().isoformat() — no timezone!

#         text_data = f"Sleep: {sleep_log.sleep} hours"
#         if sleep_log.notes:
#             text_data += f" Notes: {sleep_log.notes}"

#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"sleep_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'sleep_log',
#             'sleep': sleep_log.sleep,
#             'user_id': sleep_log.MONGODB_user,
#             'timestamp': timestamp
#         }
#         if sleep_log.notes:
#             metadata['notes'] = sleep_log.notes

#         vector_data = [{'id': log_id, 'embedding': embedding, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='sleep_log')

#         return {'status': True, 'message': 'Sleep log stored successfully', 'log_id': log_id}
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post('/pain-log')
# def log_pain(pain_log: Pain):
#     """Store pain log with embeddings in Pinecone"""
#     try:
#         if is_log_empty(pain_log):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(pain_log.timestamp)  # was: datetime.now().isoformat() — no timezone!

#         text_data = f"Pain Level: {pain_log.pain_level}"
#         if pain_log.notes:
#             text_data += f" Notes: {pain_log.notes}"

#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"pain_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'pain_log',
#             'pain_level': pain_log.pain_level,
#             'user_id': pain_log.MONGODB_user,
#             'timestamp': timestamp
#         }
#         if pain_log.notes:
#             metadata['notes'] = pain_log.notes

#         vector_data = [{'id': log_id, 'embedding': embedding, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='pain_log')

#         return {'status': True, 'message': 'Pain log stored successfully', 'log_id': log_id}
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post('/medication-log')
# def log_medication(medication: Medication):
#     """Store medication log with embeddings in Pinecone"""
#     print("Medication Log Request Data:", medication.dict())
#     print("Schema fields:", list(medication.__fields__.keys()))

#     try:
#         if is_log_empty(medication):
#             return {'status': False, 'message': 'Fields should not be zero or null.'}

#         timestamp = resolve_timestamp(medication.timestamp)

#         text_data = (
#             f"Medicine Name: {medication.name}, Dose: {medication.dose} {medication.unit}, "
#             f"Schedule Type: {medication.scheduleType}"
#         )
#         if medication.intervalDays:
#             text_data += f", Interval: {medication.intervalDays} days"
#         if medication.timesOfDay:
#             text_data += f", Times of Day: {', '.join(medication.timesOfDay)}"
#         if medication.customTimes:
#             text_data += f", Custom Times: {', '.join(medication.customTimes)}"
#         if medication.notes:
#             text_data += f", Notes: {medication.notes}"

#         embedding = embedding_service.generate_embedding(text_data)
#         if embedding is None:
#             raise HTTPException(status_code=400, detail="Failed to generate embedding")

#         log_id = f"medication_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
#         metadata = {
#             'type': 'medication_log',
#             'name': medication.name,
#             'dose': medication.dose,
#             'unit': medication.unit,
#             'scheduleType': medication.scheduleType,
#             'isActive': medication.isActive,
#             'isPriority': medication.isPriority,
#             'isTaken': medication.isTaken,
#             'takenToday': medication.takenToday,
#             'MONGODB_user': medication.MONGODB_user,
#             'timestamp': timestamp
#         }
#         if medication.intervalDays:
#             metadata['intervalDays'] = medication.intervalDays
#         if medication.timesOfDay:
#             metadata['timesOfDay'] = medication.timesOfDay
#         if medication.customTimes:
#             metadata['customTimes'] = medication.customTimes
#         if medication.notes:
#             metadata['notes'] = medication.notes
#         if medication.lastTakenDate:
#             metadata['lastTakenDate'] = medication.lastTakenDate
#         if medication.nextScheduledDate:
#             metadata['nextScheduledDate'] = medication.nextScheduledDate
#         if medication.intervalStartDate:
#             metadata['intervalStartDate'] = medication.intervalStartDate

#         vector_data = [{'id': log_id, 'embedding': embedding, 'metadata': metadata}]
#         embedding_service.upsert_vectors(vector_data, namespace='medication_log')

#         return {
#             'status': True,
#             'message': 'Medication log stored successfully',
#             'log_id': log_id,
#             'medication_data': {
#                 'name': medication.name,
#                 'dose': medication.dose,
#                 'unit': medication.unit,
#                 'scheduleType': medication.scheduleType,
#                 'isActive': medication.isActive
#             }
#         }
#     except ValueError as e:
#         return {'status': False, 'error': str(e)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))