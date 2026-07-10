from calorie_counter.tools import create_health_data_tools
from utils import get_user_by_id
from langchain.tools import tool
from langchain.agents import create_agent
import os
from openai import OpenAI
from fastapi import HTTPException,status


def get_user_details(user_id):
    """
    Retrieves user details based on the provided user ID.
    """
    user_details=get_user_by_id(user_id)
    
    get_user_dict={
    "allergy_sensitivity":user_details['allergiesSensitivities'],
    'diet_preferences':user_details['dietaryPreferences'],
    'body_weight':user_details['bodyWeightUnit'],
    'weight_unit':user_details['equipmentWeightUnit'],
    'body_lenght_unit':user_details['bodyLengthUnit'],
    'distance_unit':user_details['distanceUnit'],
    'steps_goal':user_details['stepsGoal'],
    'activity_minutes_goal':user_details['activityMinutesGoal'],
    'experience_level':user_details['experienceLevel'],
    'diet_preference':user_details['dietaryPreference'],
    'food_allergies':user_details['foodAllergies'],
    'age':user_details['age'],
    'gender':user_details['genderForCalcs'],
    'goal_type':user_details['goalType'],
    'height':user_details['height'],
    'weight':user_details['weight'],
    'injuries':user_details['injuries'],
    'medicalAlerts':user_details['medicalAlerts']
    }

    return get_user_dict


# print(get_user_details('6946c61a2c87c319dafe8835'))


def ai_coach(user_id):
    tools=create_health_data_tools(user_id)
    user_data=get_user_details(user_id)

    agent=create_agent(
        model='gpt-4o-mini',
        system_prompt=f"""You are an AI assistant you will check the users data using tools also check user data
        from this {user_data} you will get the other data of user like age weight height injuries etc based on those you should recomend the calories as well
        must execute the tools too so you will get all types of data from user.""",
        tools=tools
    )

    result=agent.invoke({'role':'user','content':user_id,'role':'system','content':'calculate the calories of user based on the available data'})
    messages=result.get('messages')
    last_message=messages[-1]
    content=last_message.content
    return content
    # invoke={'messages':[{'role':'user','content':user_id,'role':'system','content':'calculate the calories of user based on the available data'}]}
    # for chunks in agent.stream(invoke,stream_mode='updates'):
    #     # print(chunks)
    #     model=chunks.get('model')
    #     messages=model.get('messages')
    #     return messages[-1].content


# print(ai_coach('6946c61a2c87c319dafe8835'))