
from datetime import datetime
import dateutil.parser

from utils import embedding_service


def retrieve_health_data(user_id):
    """
    Retrieve all health logs for the specified user from Pinecone.
    This function searches the 'health_metrics' namespace and returns all health metrics for the user.
    """
    try:
        logs = embedding_service.search_similar(
            query_text='health metrics health activity',
            top_k=2000,
            namespace='health_metrics'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No health logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving health logs: {str(e)}")
        return {'error': str(e)}


def retrieve_water_logs(user_id):
    """Retrieve water intake logs from water_log namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='water intake hydration',
            top_k=2000,
            namespace='water_log'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No water logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving water logs: {str(e)}")
        return {'error': str(e)}


def retrieve_weight_logs(user_id):
    """Retrieve weight logs from weight_logs namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='weight body weight',
            top_k=2000,
            namespace='weight_logs'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No weight logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving weight logs: {str(e)}")
        return {'error': str(e)}


def retrieve_mood_logs(user_id):
    """Retrieve mood logs from mood_logs namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text=(
                'mood, feeling, emotion, emotional, how am I feeling, '
                'how do I feel, mood log, mood entry, mental state, '
                'my mood, my feelings, my emotions, today\'s mood, '
                'today\'s feeling, today\'s emotion'
            ),
            top_k=200,
            namespace='mood_logs'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No mood logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving mood logs: {str(e)}")
        return {'error': str(e)}


def retrieve_meal_logs(user_id):
    """Retrieve meal logs from meal_log namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='meal food nutrition',
            top_k=2000,
            namespace='meal_log'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No meal logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving meal logs: {str(e)}")
        return {'error': str(e)}


def retrieve_sleep_logs(user_id):
    """Retrieve sleep logs from sleep_log namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='sleep rest',
            top_k=2000,
            namespace='sleep_log'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('user_id') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No sleep logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving sleep logs: {str(e)}")
        return {'error': str(e)}


def retrieve_pain_logs(user_id):
    """Retrieve pain logs from pain_log namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='pain injury discomfort',
            top_k=2000,
            namespace='pain_log'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('user_id') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No pain logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving pain logs: {str(e)}")
        return {'error': str(e)}
    

def retrieve_medication_logs(user_id):
    """Retrieve medication logs from medication_log namespace"""
    try:
        logs = embedding_service.search_similar(
            query_text='medication medicine dosage',
            top_k=2000,
            namespace='medication_log'
        )
        
        all_logs = []
        if logs:
            for log in logs:
                # Handle both object (with .metadata) and dict access
                metadata = getattr(log, 'metadata', None) or log.get('metadata')
                
                if metadata:
                    if metadata.get('MONGODB_user') == user_id:
                        all_logs.append(dict(metadata))
        
        if all_logs:
            all_logs.sort(
                key=lambda x: datetime.fromisoformat(x['timestamp']) if x.get('timestamp') else datetime.min,
                reverse=True
            )
            return all_logs
        else:
            return {'error': 'No medication logs found for this user.'}
    except Exception as e:
        print(f"Error retrieving medication logs: {str(e)}")
        return {'error': str(e)}





# result=retrieve_medication_logs('6992fadc22e11e68151d252e')
# print(result)