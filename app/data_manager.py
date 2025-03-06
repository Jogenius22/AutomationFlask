import json
import os
import uuid
import time
import random
import datetime
from config import ACCOUNTS_FILE, CITIES_FILE, MESSAGES_FILE, SCHEDULES_FILE, LOGS_FILE, SETTINGS_FILE
import math

LOG_LEVEL_FILTER = os.environ.get('LOG_LEVEL_FILTER', 'automation')  # Set to 'all', 'automation', or 'essential'

def generate_id():
    """Generate a unique ID for new records"""
    return str(uuid.uuid4())

def datetime_converter(obj):
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")

def _string_to_datetime(datetime_str):
    """Safely convert ISO format string to datetime object"""
    if not datetime_str or not isinstance(datetime_str, str):
        return None
    try:
        return datetime.datetime.fromisoformat(datetime_str)
    except (ValueError, TypeError):
        # If the string isn't a valid ISO format, return None
        return None

def _read_file_with_retry(file_path, max_retries=3):
    """Read a JSON file with retry mechanism to handle transient errors"""
    retries = 0
    while retries < max_retries:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return []
        except json.JSONDecodeError as e:
            print(f"JSON error reading {file_path}: {e}. Retry {retries+1}/{max_retries}")
            retries += 1
            time.sleep(random.uniform(0.5, 2.0))  # Random backoff
            if retries == max_retries - 1:  # Last retry
                # Try to backup the corrupted file and create a new one
                backup_path = f"{file_path}.corrupted.{int(time.time())}"
                try:
                    if os.path.exists(file_path):
                        os.rename(file_path, backup_path)
                        print(f"Backed up corrupted file to {backup_path}")
                except Exception as rename_e:
                    print(f"Failed to backup corrupted file: {rename_e}")
                return []

def _write_file_with_retry(file_path, data, max_retries=3, default=None):
    """Write data to a JSON file with retry logic."""
    for attempt in range(max_retries):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f, default=default)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to write to {file_path} after {max_retries} attempts: {str(e)}")
                return False
            time.sleep(0.5)  # Wait before retrying

def get_accounts():
    """Retrieve all accounts from the accounts JSON file."""
    accounts = _read_file_with_retry(ACCOUNTS_FILE)
    # Convert string dates to datetime objects
    for account in accounts:
        if account.get('last_used') and isinstance(account['last_used'], str):
            account['last_used'] = _string_to_datetime(account['last_used'])
        if 'created_at' in account and account['created_at']:
            account['created_at'] = _string_to_datetime(account['created_at'])
    return accounts

def add_account(email, password, capsolver_key=None, active=True):
    """Add a new account to JSON file"""
    accounts = get_accounts()
    new_account = {
        'id': generate_id(),
        'email': email,
        'password': password,
        'capsolver_key': capsolver_key,
        'active': active,
        'last_used': datetime.datetime.now(),
        'created_at': datetime.datetime.now()
    }
    accounts.append(new_account)
    return _write_file_with_retry(ACCOUNTS_FILE, accounts, default=datetime_converter)

def get_cities():
    """Retrieve all cities from the cities JSON file."""
    cities = _read_file_with_retry(CITIES_FILE)
    # Convert string dates to datetime objects
    for city in cities:
        if city.get('created_at') and isinstance(city['created_at'], str):
            city['created_at'] = _string_to_datetime(city['created_at'])
    return cities

def add_city(name, radius):
    """Add a new city to JSON file"""
    cities = get_cities()
    new_city = {
        'id': generate_id(),
        'name': name,
        'radius': int(radius),
        'created_at': datetime.datetime.now()
    }
    cities.append(new_city)
    return _write_file_with_retry(CITIES_FILE, cities, default=datetime_converter)

def get_messages():
    """Retrieve all messages from the messages JSON file."""
    messages = _read_file_with_retry(MESSAGES_FILE)
    # Convert string dates to datetime objects
    for message in messages:
        if message.get('created_at') and isinstance(message['created_at'], str):
            message['created_at'] = _string_to_datetime(message['created_at'])
    return messages

def add_message(content, image=None):
    """Add a new message to JSON file"""
    messages = get_messages()
    new_message = {
        'id': generate_id(),
        'content': content,
        'image': image,
        'created_at': datetime.datetime.now()
    }
    messages.append(new_message)
    return _write_file_with_retry(MESSAGES_FILE, messages, default=datetime_converter)

def get_schedules():
    """Retrieve all schedules from the schedules JSON file."""
    schedules = _read_file_with_retry(SCHEDULES_FILE)
    # Convert string dates to datetime objects
    for schedule in schedules:
        if schedule.get('created_at') and isinstance(schedule['created_at'], str):
            schedule['created_at'] = _string_to_datetime(schedule['created_at'])
        if schedule.get('last_run') and isinstance(schedule['last_run'], str):
            schedule['last_run'] = _string_to_datetime(schedule['last_run'])
    return schedules

def add_schedule(account_id, city_id, start_time, end_time, days=None, max_tasks=5, status='active'):
    """Add a new schedule to JSON file"""
    schedules = get_schedules()
    new_schedule = {
        'id': generate_id(),
        'account_id': account_id,
        'city_id': city_id,
        'start_time': start_time,
        'end_time': end_time,
        'days': days or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        'max_tasks': max_tasks,
        'status': status,
        'active': status == 'active',
        'created_at': datetime.datetime.now()
    }
    schedules.append(new_schedule)
    return _write_file_with_retry(SCHEDULES_FILE, schedules, default=datetime_converter)

def get_logs(page=1, per_page=10, group_id=None, log_level_filter=None):
    """
    Get logs from the log file with pagination
    
    Args:
        page (int): Page number (1-indexed)
        per_page (int): Number of logs per page
        group_id (str, optional): Filter logs by group_id
        log_level_filter (str, optional): Filter logs by category ('all', 'automation', 'essential')
        
    Returns:
        dict: Dictionary with logs and pagination information
    """
    try:
        # Ensure parameters are valid
        page = max(1, int(page))
        per_page = max(1, int(per_page))
        
        # Apply default log level filter if none provided
        if not log_level_filter:
            log_level_filter = LOG_LEVEL_FILTER
        
        logs = _read_file_with_retry(LOGS_FILE)
        print(f"Successfully loaded {len(logs)} logs from {LOGS_FILE}")
            
        # Filter by group_id if provided
        if group_id:
            filtered_logs = [log for log in logs if log.get('group_id') == group_id]
            print(f"Filtered logs by group_id {group_id}: {len(filtered_logs)} of {len(logs)} logs match")
            logs = filtered_logs
            
        # Filter by category
        if log_level_filter == 'automation':
            # Only show logs from the automation process, not init/setup logs
            filtered_logs = [log for log in logs if log.get('category') in 
                            ['automation', 'essential', None]]
            logs = filtered_logs
        elif log_level_filter == 'essential':
            # Only show essential logs (success, error, warnings)
            filtered_logs = [log for log in logs if log.get('category') == 'essential' or 
                            log.get('level') in ['error', 'warning', 'success']]
            logs = filtered_logs
            
        # Sort logs by timestamp (newest first)
        logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Calculate pagination
        total_logs = len(logs)
        total_pages = math.ceil(total_logs / per_page) if total_logs > 0 else 1
        page = min(max(1, page), total_pages)
        
        # Get logs for the requested page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_logs = logs[start_idx:end_idx] if logs else []
        
        result = {
            'items': page_logs,
            'total': total_logs,
            'page': page,
            'per_page': per_page,
            'pages': total_pages
        }
        return result
    except Exception as e:
        print(f"Error getting logs: {str(e)}")
        # Return a valid structure even on error
        return {
            'items': [],
            'total': 0,
            'page': 1,
            'per_page': per_page,
            'pages': 0
        }

def add_log(message, level='info', group_id=None, category='automation'):
    """
    Add a log entry to the log file
    
    Args:
        message (str): Log message
        level (str): Log level (info, warning, error, success)
        group_id (str, optional): Group ID to associate related logs together
        category (str, optional): Category of log ('setup', 'automation', 'essential')
        
    Returns:
        dict: The log entry that was added
    """
    try:
        logs = _read_file_with_retry(LOGS_FILE)

        if message is not None:
            message = str(message)[:2000]
            message = ''.join(c if ord(c) >= 32 or c in '\n\r\t' else ' ' for c in message)

        log_entry = {
            'id': str(uuid.uuid4()),
            'message': message,
            'level': level,
            'category': category,
            'timestamp': datetime.datetime.now().isoformat()
        }

        if group_id:
            log_entry['group_id'] = group_id

        logs.append(log_entry)

        logs.sort(key=lambda x: datetime.datetime.fromisoformat(x['timestamp']), reverse=True)

        logs = logs[:1000]

        success = _write_file_with_retry(LOGS_FILE, logs, default=datetime_converter)
        if not success:
            print(f"WARNING: Could not save log: {message[:50]}...")

        return log_entry
    except Exception as e:
        print(f"Error adding log: {str(e)}")
        return {
            'id': str(uuid.uuid4()),
            'message': f"Error adding log: {str(e)}",
            'level': 'error',
            'category': 'essential',
            'timestamp': datetime.datetime.now().isoformat()
        }

def get_settings():
    """Get application settings"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {
        "run_interval": 30,
        "max_posts_per_day": 10,
        "timeout_between_actions": 5,
        "enable_random_delays": True
    }

def update_settings(settings_data):
    """Update application settings"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings_data, f, indent=4)
    return settings_data

def get_account_by_id(account_id):
    """Get an account by its ID"""
    accounts = get_accounts()
    for account in accounts:
        if account['id'] == account_id:
            return account
    return None

def get_city_by_id(city_id):
    """Get city by ID"""
    cities = get_cities()
    for city in cities:
        if city['id'] == city_id:
            return city
    return None

def get_message_by_id(message_id):
    """Get message by ID"""
    messages = get_messages()
    for message in messages:
        if message['id'] == message_id:
            return message
    return None

def update_account_last_used(account_id):
    """Update the last_used field of an account to the current datetime."""
    try:
        accounts = get_accounts()
        for account in accounts:
            if account['id'] == account_id:
                account['last_used'] = datetime.datetime.now()
                return _write_file_with_retry(ACCOUNTS_FILE, accounts, default=datetime_converter)
        return False
    except Exception as e:
        print(f"Error updating account last used: {str(e)}")
        return False

def delete_account(account_id):
    """Delete an account by ID"""
    accounts = get_accounts()
    accounts = [account for account in accounts if account['id'] != account_id]
    return _write_file_with_retry(ACCOUNTS_FILE, accounts, default=datetime_converter)

def delete_city(city_id):
    """Delete a city by ID"""
    cities = get_cities()
    cities = [city for city in cities if city['id'] != city_id]
    return _write_file_with_retry(CITIES_FILE, cities, default=datetime_converter)

def delete_message(message_id):
    """Delete a message by ID"""
    messages = get_messages()
    # Find the message to delete and get its image filename if it exists
    image_to_delete = None
    for message in messages:
        if message['id'] == message_id and message.get('image'):
            image_to_delete = message['image']
            break
    
    # Filter out the message to be deleted
    messages = [message for message in messages if message['id'] != message_id]
    
    return _write_file_with_retry(MESSAGES_FILE, messages, default=datetime_converter)

def delete_schedule(schedule_id):
    """Delete a schedule by ID"""
    schedules = get_schedules()
    schedules = [schedule for schedule in schedules if schedule['id'] != schedule_id]
    return _write_file_with_retry(SCHEDULES_FILE, schedules, default=datetime_converter)

def update_last_used(account_id):
    """Update the last_used timestamp for an account"""
    accounts = get_accounts()
    for account in accounts:
        if account['id'] == account_id:
            account['last_used'] = datetime.datetime.now().isoformat()
            return _write_file_with_retry(ACCOUNTS_FILE, accounts, default=datetime_converter)
    return False

def update_account(account_id, **kwargs):
    """Update an existing account"""
    accounts = get_accounts()
    for account in accounts:
        if account.get('id') == account_id:
            account.update(kwargs)
            return _write_file_with_retry(ACCOUNTS_FILE, accounts, default=datetime_converter)
    return False

def update_city(city_id, **kwargs):
    """Update an existing city"""
    cities = get_cities()
    for city in cities:
        if city.get('id') == city_id:
            city.update(kwargs)
            return _write_file_with_retry(CITIES_FILE, cities, default=datetime_converter)
    return False

def update_message(message_id, **kwargs):
    """Update a message by ID with provided fields"""
    messages = get_messages()
    for message in messages:
        if message['id'] == message_id:
            for key, value in kwargs.items():
                message[key] = value
            return _write_file_with_retry(MESSAGES_FILE, messages, default=datetime_converter)
    return False

def update_schedule(schedule_id, **kwargs):
    """Update a schedule by ID with provided fields"""
    schedules = get_schedules()
    for schedule in schedules:
        if schedule['id'] == schedule_id:
            for key, value in kwargs.items():
                schedule[key] = value
            return _write_file_with_retry(SCHEDULES_FILE, schedules, default=datetime_converter)
    return False

class LogManager:
    """Class to manage log operations with enhanced functionality"""
    
    def __init__(self):
        self.logs_file = LOGS_FILE
    
    def get_logs(self, limit=None, offset=0, group_id=None, log_level_filter=None):
        """
        Get logs with more flexible options for API endpoints
        
        Args:
            limit (int, optional): Maximum number of logs to return
            offset (int, optional): Number of logs to skip
            group_id (str, optional): Filter logs by group_id
            log_level_filter (str, optional): Filter logs by category ('all', 'automation', 'essential')
            
        Returns:
            list: List of log entries
        """
        try:
            # Apply default log level filter if none provided
            if not log_level_filter:
                log_level_filter = LOG_LEVEL_FILTER
            
            logs = _read_file_with_retry(self.logs_file)
            if logs is None:
                return []
                
            # Filter by group_id if provided
            if group_id:
                logs = [log for log in logs if log.get('group_id') == group_id]
                
            # Filter by category
            if log_level_filter == 'automation':
                # Only show logs from the automation process, not init/setup logs
                logs = [log for log in logs if log.get('category') in 
                        ['automation', 'essential', None]]
            elif log_level_filter == 'essential':
                # Only show essential logs (success, error, warnings)
                logs = [log for log in logs if log.get('category') == 'essential' or 
                        log.get('level') in ['error', 'warning', 'success']]
                
            # Sort logs by timestamp (newest first)
            logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Apply offset and limit
            if offset > 0:
                logs = logs[offset:]
            if limit is not None:
                logs = logs[:limit]
            
            return logs
            
        except Exception as e:
            print(f"LogManager: Error getting logs: {str(e)}")
            return []
    
    def count_logs(self, group_id=None, log_level_filter=None):
        """
        Count the total number of logs matching the filters
        
        Args:
            group_id (str, optional): Filter logs by group_id
            log_level_filter (str, optional): Filter logs by category
            
        Returns:
            int: Total number of logs
        """
        try:
            # Apply default log level filter if none provided
            if not log_level_filter:
                log_level_filter = LOG_LEVEL_FILTER
            
            logs = _read_file_with_retry(self.logs_file)
            if logs is None:
                return 0
                
            # Filter by group_id if provided
            if group_id:
                logs = [log for log in logs if log.get('group_id') == group_id]
                
            # Filter by category
            if log_level_filter == 'automation':
                logs = [log for log in logs if log.get('category') in 
                        ['automation', 'essential', None]]
            elif log_level_filter == 'essential':
                logs = [log for log in logs if log.get('category') == 'essential' or 
                        log.get('level') in ['error', 'warning', 'success']]
            
            return len(logs)
            
        except Exception as e:
            print(f"LogManager: Error counting logs: {str(e)}")
            return 0 