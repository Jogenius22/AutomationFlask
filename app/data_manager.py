import json
import os
import uuid
import time
import random
from datetime import datetime
from config import ACCOUNTS_FILE, CITIES_FILE, MESSAGES_FILE, SCHEDULES_FILE, LOGS_FILE, SETTINGS_FILE
import math

LOG_LEVEL_FILTER = os.environ.get('LOG_LEVEL_FILTER', 'automation')  # Set to 'all', 'automation', or 'essential'

def generate_id():
    """Generate a unique ID for new records"""
    return str(uuid.uuid4())

def datetime_converter(obj):
    """Convert datetime objects to ISO format for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

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

def _write_file_with_retry(file_path, data, max_retries=3):
    """Write data to a JSON file with retry mechanism for resilience"""
    # First, ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    retries = 0
    while retries < max_retries:
        try:
            # Write to a temporary file first
            temp_file = f"{file_path}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=4, default=datetime_converter)
                # Force flush to disk inside the with block to ensure file is not closed prematurely
                f.flush()
                os.fsync(f.fileno())
            
            # Rename to actual file (atomic operation on most filesystems)
            os.replace(temp_file, file_path)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}. Retry {retries+1}/{max_retries}")
            retries += 1
            time.sleep(random.uniform(0.5, 2.0))  # Random backoff
    
    print(f"Failed to write to {file_path} after {max_retries} attempts")
    return False

def get_accounts():
    """Get all accounts from JSON file"""
    return _read_file_with_retry(ACCOUNTS_FILE)

def add_account(email, password, active=True):
    """Add a new account to JSON file"""
    accounts = get_accounts()
    new_account = {
        'id': generate_id(),
        'email': email,
        'password': password,
        'active': active,
        'last_used': None,
        'created_at': datetime.utcnow()
    }
    accounts.append(new_account)
    _write_file_with_retry(ACCOUNTS_FILE, accounts)
    return new_account

def get_cities():
    """Get all cities from JSON file"""
    return _read_file_with_retry(CITIES_FILE)

def add_city(name, radius):
    """Add a new city to JSON file"""
    cities = get_cities()
    new_city = {
        'id': generate_id(),
        'name': name,
        'radius': int(radius),
        'created_at': datetime.utcnow()
    }
    cities.append(new_city)
    _write_file_with_retry(CITIES_FILE, cities)
    return new_city

def get_messages():
    """Get all messages from JSON file"""
    return _read_file_with_retry(MESSAGES_FILE)

def add_message(content, image=None):
    """Add a new message to JSON file"""
    messages = get_messages()
    new_message = {
        'id': generate_id(),
        'content': content,
        'image': image,
        'created_at': datetime.utcnow(),
        'last_used': None
    }
    messages.append(new_message)
    _write_file_with_retry(MESSAGES_FILE, messages)
    return new_message

def get_schedules():
    """Get all schedules from JSON file"""
    return _read_file_with_retry(SCHEDULES_FILE)

def add_schedule(start_time, end_time, active=True):
    """Add a new schedule to JSON file"""
    schedules = get_schedules()
    new_schedule = {
        'id': generate_id(),
        'start_time': start_time,
        'end_time': end_time,
        'active': active,
        'created_at': datetime.utcnow()
    }
    schedules.append(new_schedule)
    _write_file_with_retry(SCHEDULES_FILE, schedules)
    return new_schedule

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
        # Load existing logs or create empty list
        logs = _read_file_with_retry(LOGS_FILE)
        
        # Sanitize message for JSON compatibility
        if message is not None:
            # Limit message length
            message = str(message)[:2000]
            # Replace control characters that would break JSON
            message = ''.join(c if ord(c) >= 32 or c in '\n\r\t' else ' ' for c in message)
        
        # Create new log entry
        log_entry = {
            'id': str(uuid.uuid4()),
            'message': message,
            'level': level,
            'category': category,
            'timestamp': datetime.now()  # Use datetime object directly
        }
        
        # Add group_id if provided
        if group_id:
            log_entry['group_id'] = group_id
        
        # Append new log
        logs.append(log_entry)
        
        # Sort logs by timestamp (newest first)
        logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Keep only the last 1000 logs to prevent file growth
        logs = logs[:1000]
        
        # Write logs back to file
        success = _write_file_with_retry(LOGS_FILE, logs)
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
            'timestamp': datetime.now()  # Use datetime object directly
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
    """Update last_used timestamp for account"""
    accounts = get_accounts()
    for account in accounts:
        if account['id'] == account_id:
            account['last_used'] = datetime.utcnow()  # Use datetime object directly
            break
    
    _write_file_with_retry(ACCOUNTS_FILE, accounts)

def delete_account(account_id):
    """Delete an account by ID"""
    accounts = get_accounts()
    accounts = [account for account in accounts if account['id'] != account_id]
    _write_file_with_retry(ACCOUNTS_FILE, accounts)
    return True

def delete_city(city_id):
    """Delete a city by ID"""
    cities = get_cities()
    cities = [city for city in cities if city['id'] != city_id]
    _write_file_with_retry(CITIES_FILE, cities)
    return True

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
    
    _write_file_with_retry(MESSAGES_FILE, messages)
    
    # Return the image filename if it exists, so it can be deleted from the filesystem
    return image_to_delete

def delete_schedule(schedule_id):
    """Delete a schedule by ID"""
    schedules = get_schedules()
    schedules = [schedule for schedule in schedules if schedule['id'] != schedule_id]
    _write_file_with_retry(SCHEDULES_FILE, schedules)
    return True

def update_last_used(account_id):
    """Update the last_used timestamp for an account"""
    accounts = get_accounts()
    for account in accounts:
        if account['id'] == account_id:
            account['last_used'] = datetime.utcnow().isoformat()
            _write_file_with_retry(ACCOUNTS_FILE, accounts)
            return True
    return False

def update_account(account_id, **kwargs):
    """Update an existing account"""
    accounts = get_accounts()
    for account in accounts:
        if account.get('id') == account_id:
            account.update(kwargs)
            _write_file_with_retry(ACCOUNTS_FILE, accounts)
            return account
    return None

def update_city(city_id, **kwargs):
    """Update an existing city"""
    cities = get_cities()
    for city in cities:
        if city.get('id') == city_id:
            city.update(kwargs)
            _write_file_with_retry(CITIES_FILE, cities)
            return city
    return None

def update_message(message_id, **kwargs):
    """Update a message by ID with provided fields"""
    messages = get_messages()
    for message in messages:
        if message['id'] == message_id:
            for key, value in kwargs.items():
                message[key] = value
            _write_file_with_retry(MESSAGES_FILE, messages)
            return True
    return False

def update_schedule(schedule_id, **kwargs):
    """Update a schedule by ID with provided fields"""
    schedules = get_schedules()
    for schedule in schedules:
        if schedule['id'] == schedule_id:
            for key, value in kwargs.items():
                schedule[key] = value
            _write_file_with_retry(SCHEDULES_FILE, schedules)
            return True
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