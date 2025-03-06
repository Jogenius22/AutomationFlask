import os
import json
import re
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from app.forms import AccountForm, CityForm, MessageForm, ScheduleForm, SettingsForm
from app.data_manager import add_account, get_accounts, add_city, get_cities, add_message, get_messages
from app.data_manager import add_schedule, get_schedules, add_log, get_account_by_id, update_account, update_city
from app.data_manager import update_message, update_schedule, delete_account, delete_city, delete_message
from app.data_manager import delete_schedule, get_settings, update_settings, LogManager
import app.data_manager as dm
from app.tasks import start_bot_task
from config import SCREENSHOTS_DIR

import time
from datetime import datetime, time

bp = Blueprint('main', __name__)

class Pagination:
    """Helper class for pagination that can be initialized with either a dictionary or direct parameters"""
    def __init__(self, data=None, page=1, per_page=10, total=0, items=None):
        if data is not None and isinstance(data, dict):
            # Initialize from dictionary (old format)
            self.page = data.get('page', 1)
            self.per_page = data.get('per_page', 10)
            self.total = data.get('total', 0)
            self.items = data.get('items', [])
            self.pages = data.get('pages', 0) or self._calculate_pages()
        else:
            # Initialize from parameters (new format)
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items or []
            self.pages = self._calculate_pages()
    
    def _calculate_pages(self):
        """Calculate the total number of pages"""
        return max(1, (self.total + self.per_page - 1) // self.per_page)
    
    def has_prev(self):
        """Check if there is a previous page"""
        return self.page > 1
    
    def has_next(self):
        """Check if there is a next page"""
        return self.page < self.pages
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
        """Iterate over page numbers with sensible defaults"""
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (num > self.page - left_current - 1 and num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@bp.route('/')
@bp.route('/dashboard')
def dashboard():
    """Dashboard with account, city, message management and recent logs"""
    # Initialize with empty values to handle exceptions gracefully
    accounts = []
    cities = []
    messages = []
    logs = Pagination(page=1, per_page=5, total=0, items=[])
    
    # Get settings with a fallback for error cases
    try:
        settings = dm.get_settings()
    except Exception as e:
        current_app.logger.error(f"Error loading settings: {str(e)}")
        settings = {"max_posts_per_day": 3}  # Default fallback settings
    
    try:
        # Get accounts, cities, and messages for the dashboard
        accounts = get_accounts()
        cities = get_cities()
        messages = get_messages()
        
        # Get latest logs for the recent activity section
        try:
            log_manager = LogManager()
            logs_data = log_manager.get_logs(limit=5)  # Just get the latest 5 logs
            
            # Create pagination object for consistency
            logs = Pagination(page=1, per_page=5, total=len(logs_data) if logs_data else 0, items=logs_data)
        except Exception as e:
            current_app.logger.error(f"Error loading logs: {e}")
            logs = Pagination(page=1, per_page=5, total=0, items=[])
        
        # Check if this is an AJAX request for auto-refresh
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'logs': logs_data
            })
    except Exception as e:
        error_msg = f"Error loading dashboard: {str(e)}"
        current_app.logger.error(error_msg)
        flash(error_msg, 'danger')
    
    # Always return a template with whatever data we have, including settings
    return render_template('dashboard.html', 
                          accounts=accounts,
                          cities=cities, 
                          messages=messages,
                          logs=logs,
                          settings=settings,
                          title="Dashboard")

@bp.route('/accounts', methods=['GET', 'POST'])
def accounts():
    form = AccountForm()
    if form.validate_on_submit():
        dm.add_account(
            email=form.email.data,
            password=form.password.data,
            active=form.active.data
        )
        flash('Account added successfully', 'success')
        return redirect(url_for('main.accounts'))
    
    accounts = dm.get_accounts()
    
    # Convert any string dates to datetime objects for the template
    for account in accounts:
        if account.get('last_used') and isinstance(account['last_used'], str):
            try:
                account['last_used'] = datetime.fromisoformat(account['last_used'])
            except ValueError:
                account['last_used'] = None
        
        if account.get('created_at') and isinstance(account['created_at'], str):
            try:
                account['created_at'] = datetime.fromisoformat(account['created_at'])
            except ValueError:
                account['created_at'] = None
    
    return render_template('accounts.html', form=form, accounts=accounts)

@bp.route('/cities', methods=['GET', 'POST'])
def cities():
    form = CityForm()
    if form.validate_on_submit():
        dm.add_city(
            name=form.name.data,
            radius=form.radius.data
        )
        flash('City added successfully', 'success')
        return redirect(url_for('main.cities'))
    
    cities = dm.get_cities()
    
    # Convert any string dates to datetime objects for the template
    for city in cities:
        if city.get('created_at') and isinstance(city['created_at'], str):
            try:
                city['created_at'] = datetime.fromisoformat(city['created_at'])
            except ValueError:
                city['created_at'] = None
    
    return render_template('cities.html', form=form, cities=cities)

@bp.route('/messages', methods=['GET', 'POST'])
def messages():
    form = MessageForm()
    if form.validate_on_submit():
        image_filename = None
        
        # Handle image upload
        if form.image.data:
            image = form.image.data
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_filename = filename
                image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        
        dm.add_message(
            content=form.content.data,
            image=image_filename
        )
        flash('Message added successfully', 'success')
        return redirect(url_for('main.messages'))
    
    messages = dm.get_messages()
    
    # Convert any string dates to datetime objects for the template
    for message in messages:
        if message.get('created_at') and isinstance(message['created_at'], str):
            try:
                message['created_at'] = datetime.fromisoformat(message['created_at'])
            except ValueError:
                message['created_at'] = None
        
        if message.get('last_used') and isinstance(message['last_used'], str):
            try:
                message['last_used'] = datetime.fromisoformat(message['last_used'])
            except ValueError:
                message['last_used'] = None
    
    return render_template('messages.html', form=form, messages=messages)

@bp.route('/schedules', methods=['GET', 'POST'])
def schedules():
    form = ScheduleForm()
    if form.validate_on_submit():
        dm.add_schedule(
            start_time=form.start_time.data.strftime('%H:%M'),
            end_time=form.end_time.data.strftime('%H:%M'),
            active=form.active.data
        )
        flash('Schedule added successfully', 'success')
        return redirect(url_for('main.schedules'))
    
    schedules = dm.get_schedules()
    
    # Format datetime fields for display
    for schedule in schedules:
        if schedule.get('created_at') and isinstance(schedule['created_at'], str):
            try:
                schedule['created_at'] = datetime.fromisoformat(schedule['created_at'])
            except ValueError:
                schedule['created_at'] = None
                
        if schedule.get('start_time'):
            try:
                parts = schedule['start_time'].split(':')
                schedule['start_time'] = time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                schedule['start_time'] = None
                
        if schedule.get('end_time'):
            try:
                parts = schedule['end_time'].split(':')
                schedule['end_time'] = time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                schedule['end_time'] = None
    
    return render_template('schedules.html', form=form, schedules=schedules)

@bp.route('/start', methods=['POST'])
def start_bot():
    try:
        city_id = request.form.get('city')
        message_id = request.form.get('message')
        account_id = request.form.get('account')
        max_posts = request.form.get('max_posts', '3')  # Default to 3 if not provided
        
        # Validate max_posts is a valid integer
        try:
            max_posts = int(max_posts)
            if max_posts < 1:
                max_posts = 1
            elif max_posts > 20:
                max_posts = 20
        except (ValueError, TypeError):
            max_posts = 3  # Default to 3 if not a valid number
        
        # Get the actual objects from our data files
        account = dm.get_account_by_id(account_id)
        city = dm.get_city_by_id(city_id)
        message = dm.get_message_by_id(message_id)
        
        if not account or not city or not message:
            flash('Missing required selections for bot operation', 'danger')
            return redirect(url_for('main.dashboard'))
        
        # Log the attempt
        dm.add_log(f"Bot started for {account['email']} in {city['name']} with max posts: {max_posts}", 'info')
        
        # Start the bot in a background thread
        start_bot_task(account_id=account_id, city_id=city_id, message_id=message_id, max_posts=max_posts)
        
        flash(f'Bot started successfully with {account["email"]} in {city["name"]}!', 'success')
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        flash(f'Error starting bot: {str(e)}', 'danger')
        return redirect(url_for('main.dashboard'))

@bp.route('/logs', methods=['GET'])
def logs():
    try:
        per_page = 20
        page = request.args.get('page', 1, type=int)
        group_id = request.args.get('group_id')
        
        log_manager = LogManager()
        
        # If group_id is provided, get logs for that specific group
        if group_id:
            logs_data = log_manager.get_logs(group_id=group_id)
            
            # Convert any string timestamps to datetime objects
            for log in logs_data:
                if log.get('timestamp') and isinstance(log['timestamp'], str):
                    try:
                        log['timestamp'] = datetime.fromisoformat(log['timestamp'])
                    except ValueError:
                        log['timestamp'] = None
            
            # Extract account info if this is a bot start log group
            account_info = {}
            if logs_data and isinstance(logs_data, list):
                for log in logs_data:
                    if 'Starting bot with account' in log.get('message', ''):
                        # Extract account details from the message
                        message = log.get('message', '')
                        try:
                            # Find the JSON part in the message
                            import re
                            import json
                            json_match = re.search(r'\{.*\}', message)
                            if json_match:
                                account_data = json.loads(json_match.group(0))
                                account_info = account_data
                        except Exception as e:
                            current_app.logger.error(f"Error extracting account info: {str(e)}")
            
            # Paginate the logs
            total_logs = len(logs_data) if logs_data else 0
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_logs)
            logs_subset = logs_data[start_idx:end_idx] if logs_data else []
            
            # Create a pagination object
            logs_pagination = Pagination(page=page, 
                                         per_page=per_page, 
                                         total=total_logs, 
                                         items=logs_subset)
            
            return render_template('logs.html', 
                                  logs=logs_pagination, 
                                  group_id=group_id,
                                  account_info=account_info,
                                  title=f"Bot Run Logs - {group_id[:8]}")
        
        # Otherwise, get general logs
        else:
            # Get the latest logs
            logs_data = log_manager.get_logs(limit=1000)  # Get a large number to find all groups
            
            # Convert any string timestamps to datetime objects
            for log in logs_data:
                if log.get('timestamp') and isinstance(log['timestamp'], str):
                    try:
                        log['timestamp'] = datetime.fromisoformat(log['timestamp'])
                    except ValueError:
                        log['timestamp'] = None
            
            # Find unique group IDs for bot runs
            bot_runs = []
            group_ids = set()
            if logs_data and isinstance(logs_data, list):
                for log in logs_data:
                    group_id = log.get('group_id')
                    if group_id and group_id not in group_ids:
                        group_ids.add(group_id)
                        timestamp = log.get('timestamp')
                        
                        # Look for account name
                        account_name = "Unknown"
                        if 'Starting bot with account' in log.get('message', ''):
                            message = log.get('message', '')
                            try:
                                import re
                                import json
                                json_match = re.search(r'\{.*\}', message)
                                if json_match:
                                    account_data = json.loads(json_match.group(0))
                                    account_name = account_data.get('username', 'Unknown')
                            except Exception as e:
                                pass
                                
                        bot_runs.append({
                            'group_id': group_id,
                            'timestamp': timestamp,
                            'account_name': account_name
                        })
            
            # Sort bot runs by timestamp (newest first)
            bot_runs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Paginate the general logs
            logs_data = log_manager.get_logs(limit=per_page, offset=(page-1)*per_page)
            
            # Convert any string timestamps to datetime objects
            for log in logs_data:
                if log.get('timestamp') and isinstance(log['timestamp'], str):
                    try:
                        log['timestamp'] = datetime.fromisoformat(log['timestamp'])
                    except ValueError:
                        log['timestamp'] = None
                        
            total_logs = log_manager.count_logs()
            
            # Create a pagination object
            logs_pagination = Pagination(page=page, 
                                         per_page=per_page, 
                                         total=total_logs, 
                                         items=logs_data)
            
            return render_template('logs.html', 
                                  logs=logs_pagination, 
                                  bot_runs=bot_runs[:10],  # Show only the 10 most recent bot runs
                                  title="System Logs")
    
    except Exception as e:
        error_msg = f"Error retrieving logs: {str(e)}"
        current_app.logger.error(error_msg)
        flash(error_msg, 'danger')
        return render_template('logs.html', 
                              logs=Pagination(page=1, per_page=per_page, total=0, items=[]),
                              error=error_msg,
                              title="Logs - Error")

@bp.route('/api/recent_logs')
def api_recent_logs():
    """API endpoint to get recent logs for AJAX auto-refresh."""
    try:
        log_manager = LogManager()
        logs_data = log_manager.get_logs(limit=20)  # Get the 20 most recent logs
        
        # Convert datetime objects to strings for JSON serialization
        for log in logs_data:
            if log.get('timestamp') and not isinstance(log['timestamp'], str):
                try:
                    log['timestamp'] = log['timestamp'].isoformat()
                except AttributeError:
                    log['timestamp'] = str(log['timestamp'])
        
        # Return JSON response
        return jsonify({
            'status': 'success',
            'logs': logs_data
        })
    except Exception as e:
        error_msg = f"Error retrieving logs: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'logs': []
        }), 500

@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    current_settings = dm.get_settings()
    form = SettingsForm()
    
    if request.method == 'GET':
        # Populate form with current settings
        form.run_interval.data = current_settings.get('run_interval', 30)
        form.max_posts_per_day.data = current_settings.get('max_posts_per_day', 10)
        form.timeout_between_actions.data = current_settings.get('timeout_between_actions', 5)
        form.enable_random_delays.data = current_settings.get('enable_random_delays', True)
    
    if form.validate_on_submit():
        # Update settings
        updated_settings = {
            'run_interval': form.run_interval.data,
            'max_posts_per_day': form.max_posts_per_day.data,
            'timeout_between_actions': form.timeout_between_actions.data,
            'enable_random_delays': form.enable_random_delays.data
        }
        dm.update_settings(updated_settings)
        flash('Settings updated successfully', 'success')
        return redirect(url_for('main.settings'))
    
    return render_template('settings.html', form=form)

@bp.route('/account/delete/<account_id>', methods=['POST'])
def delete_account(account_id):
    dm.delete_account(account_id)
    flash('Account deleted successfully', 'success')
    return redirect(url_for('main.accounts'))

@bp.route('/city/delete/<city_id>', methods=['POST'])
def delete_city(city_id):
    dm.delete_city(city_id)
    flash('City deleted successfully', 'success')
    return redirect(url_for('main.cities'))

@bp.route('/message/delete/<message_id>', methods=['POST'])
def delete_message(message_id):
    image_filename = dm.delete_message(message_id)
    
    # Delete the associated image file if it exists
    if image_filename:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    flash('Message deleted successfully', 'success')
    return redirect(url_for('main.messages'))

@bp.route('/schedule/delete/<schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    dm.delete_schedule(schedule_id)
    flash('Schedule deleted successfully', 'success')
    return redirect(url_for('main.schedules'))

@bp.route('/screenshots')
def screenshots():
    # Get all PNG files from the screenshots directory
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)  # Ensure directory exists
    
    screenshots = []
    
    if os.path.exists(SCREENSHOTS_DIR):
        # Get all PNG files with creation time
        for filename in os.listdir(SCREENSHOTS_DIR):
            if filename.lower().endswith('.png'):
                filepath = os.path.join('/screenshot', filename)
                try:
                    created_at = datetime.fromtimestamp(
                        os.path.getctime(os.path.join(SCREENSHOTS_DIR, filename))
                    )
                    
                    # Try to extract a descriptive name
                    name_parts = filename.split('_')
                    if len(name_parts) > 0:
                        description = name_parts[0].replace('_', ' ').title()
                    else:
                        description = "Screenshot"
                        
                    screenshots.append({
                        'filename': filename,
                        'filepath': filepath,
                        'created_at': created_at,
                        'description': description
                    })
                except Exception as e:
                    current_app.logger.error(f"Error processing screenshot {filename}: {str(e)}")
        
        # Sort screenshots by creation time (newest first)
        screenshots.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('screenshots.html', screenshots=screenshots)

@bp.route('/screenshot/<filename>')
def get_screenshot(filename):
    return send_from_directory(SCREENSHOTS_DIR, filename)

@bp.route('/screenshots/<path:filename>')
def screenshots_file(filename):
    """Serve screenshot files"""
    try:
        return send_from_directory(SCREENSHOTS_DIR, filename)
    except Exception as e:
        error_msg = f"Error serving screenshot {filename}: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({'error': error_msg}), 404 