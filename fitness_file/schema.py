from pydantic import BaseModel
from typing import Optional, List, Union
from datetime import datetime
import uuid
from typing import Literal


class SubSet(BaseModel):
    label: Optional[str]=None
    reps: Optional[int]=None
    weight: Optional[int]=None
    completed: bool


class StandardSet(BaseModel):
    setType: Literal["Standard"] 
    setNumber: Optional[int]=None
    reps: Optional[int] = 0  # Allow None or default to 0
    weight: Optional[int] = 0
    unit: Optional[str] = None
    completed: bool


class AdvancedSet(BaseModel):
    setType: Literal["Dropset", "Superset"]   # "Drop Set" or "Super Set"
    setNumber: Optional[int]=None
    subSets: Optional[List[SubSet]]=None


class Exercise(BaseModel):
    id: str
    name: str
    bodyParts: str  # Added from metadata
    equipments: str   # Added from metadata (note: fixed typo from "quipment")
    gifUrl: str     # Added from metadata
    secondaryMuscles: str  # Added from 
    instructions:Optional[str]=None   # Added from 
    targetMuscles: str     # Added from metadata
    sets: int
    summary:str
    repsRange: str
    weightRange: str
    type: str
    setsList: List[Union[StandardSet, AdvancedSet]]


class WorkoutPlan(BaseModel):
    id: str
    day:str
    title: str
    date: str  # ISO format datetime string
    durationMinutes: int
    level: str
    category: str
    notes: str
    exercises: List[Exercise]


class WorkoutPlanContainer(BaseModel):
    workoutPlan: WorkoutPlan



