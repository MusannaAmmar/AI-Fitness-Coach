from fitness_file.logs.router import router as log_router
from chatbot.router import router as chatbot_router
from fitness_file.exercise_router import router as plannerrouter
from dotenv import load_dotenv
import os
load_dotenv()
from fastapi import FastAPI
from fastapi import FastAPI,HTTPException, Header, status
from daily_action.router import router as daily_action_router
from calorie_counter.router import router as calorie_counter_router


app=FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Fitness AI Coach API",
        "status": "active"
    }

app.include_router(log_router,prefix="/api",  tags=["Logs"])
app.include_router(chatbot_router,prefix="/api",tags=["Chat"])
app.include_router(plannerrouter,prefix='/api',tags=['Plan'])
app.include_router(daily_action_router,prefix='/api',tags=['Plan'])
app.include_router(calorie_counter_router,prefix='/api',tags=['Plan'])


