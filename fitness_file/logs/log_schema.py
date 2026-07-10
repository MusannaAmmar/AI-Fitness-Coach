from pydantic import  BaseModel, Field
import time
from typing import Optional


class WaterLog(BaseModel):
    unit: str = Field(..., description="Unit of water measurement (e.g., 'ml', 'oz', 'cups')")
    quantity: int = Field(..., description="Amount of water consumed")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")

class MealLog(BaseModel):
    meal_name: str = Field(..., description="Name of the meal")
    time: Optional[str] = Field(None, description="Time of the meal")
    calories: int = Field(..., description="Calories in the meal")
    protein: int = Field(..., description="Protein content in grams")
    fats: int = Field(..., description="Fat content in grams")
    carbs: int = Field(..., description="Carbohydrate content in grams")
    photo: Optional[str] = Field(None, description="URL or path to meal photo")
    notes: Optional[str] = Field(None, description="Additional notes about the meal")
    ratings: Optional[int] = Field(None, description="Rating for the meal (1-5)")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")


class MoodLog(BaseModel):
    mood_level: str = Field(..., description="Mood level (e.g., 'happy', 'sad', 'anxious', 'calm')")
    notes: Optional[str] = Field(None, description="Additional notes about the mood")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")


class WeightLog(BaseModel):
    quantity: int = Field(..., description="Weight value")
    units: str = Field(..., description="Unit of weight (e.g., 'kg', 'lbs')")
    notes: Optional[str] = Field(None, description="Additional notes about the weight measurement")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")



class HealthMetricsLog(BaseModel):
    sleep: Optional[float] = Field(None, description="Hours of sleep")
    heart_rate: Optional[int] = Field(None, description="Heart rate in beats per minute (bpm)")
    hydration: Optional[int] = Field(None, description="Water intake log (uses WaterLog schema)")
    steps: Optional[int] = Field(None, description="Daily steps count")
    workouts: Optional[int] = Field(None, description="Number of workouts completed")
    body_weight: Optional[int] = Field(None, description="Body weight log (uses WeightLog schema)")
    calories_burned: Optional[int] = Field(None, description="Total calories burned")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")



class Sleep(BaseModel):
    sleep:float
    notes:Optional[str]=None
    MONGODB_user:str
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")



class Pain(BaseModel):
    pain_level:float
    notes:Optional[str]=None
    MONGODB_user:str
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")


class Medication(BaseModel):
    name: str = Field(..., description="Medication name", min_length=1, max_length=255)
    dose: str = Field(..., description="Dose value (must be a positive number)")
    unit: str = Field(..., description="Unit of measurement (mg, ml, tablet, etc.)")
    scheduleType: str = Field(..., description="Schedule type (daily, weekly, interval, as_needed)")
    intervalDays: Optional[int] = Field(None, description="Number of days between doses for interval schedules")
    timesOfDay: list[str] = Field(default_factory=list, description="Times of day to take medication (morning, afternoon, evening, night)")
    customTimes: list[str] = Field(default_factory=list, description="Custom time strings for medication intake")
    notes: Optional[str] = Field(None, description="Additional notes about the medication", max_length=500)
    isPriority: bool = Field(default=False, description="Whether this is a priority medication")
    isActive: bool = Field(default=True, description="Whether the medication is currently active")
    isTaken: bool = Field(default=False, description="Whether the medication has been taken")
    takenToday: bool = Field(default=False, description="Whether the medication was taken today")
    lastTakenDate: Optional[str] = Field(None, description="ISO format date of last intake")
    nextScheduledDate: Optional[str] = Field(None, description="ISO format date of next scheduled intake")
    intervalStartDate: Optional[str] = Field(None, description="ISO format date when interval tracking started")
    MONGODB_user: str = Field(..., description="MongoDB user ID to associate this log with", example="507f1f77bcf86cd799439011")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to current time)")

