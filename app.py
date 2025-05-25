import os
import sys
import json
import time
import subprocess
import threading
import logging
import tempfile
from datetime import datetime
from queue import Queue, Empty
from functools import wraps
from typing import Dict, Any, Tuple, Optional, List
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import shared configuration
from config import AppConfig

# Configure logging based on environment
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("telegram_gift_transfer_app")

app = Flask(__name__)

# Rate limiter configuration
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Create a minimal valid configuration for startup
try:
    # Try to load the full configuration
    app_config = AppConfig.load()
except Exception as e:
    logger.warning(f"Could not load full configuration: {str(e)}")
    # Create a minimal valid configuration with defaults
    app_config = AppConfig(
        BOT_TOKEN="0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        BUSINESS_CONNECTION_ID="0000000000",
        TARGET_CHAT_ID=1,  # Use a valid default value (>0)
        LOG_DIR="logs"
    )

LOG_DIR = app_config.LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)

# Global variables to store process information
current_process = None
current_log_file = None
output_queue = Queue()
process_running = False

# Security - API key authentication
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = app_config.API_KEY
        # Skip authentication if API_KEY is not set
        if expected_key and api_key != expected_key:
            return jsonify({"success": False, "message": "Invalid or missing API key."}), 401
        return f(*args, **kwargs)
    return decorated

# Input validation functions
def validate_input(data: Dict) -> Tuple[bool, Any]:
    """
    Validate input parameters from the form submission using AppConfig.
    
    Args:
        data: Form data dictionary
        
    Returns:
        Tuple[bool, Any]: (is_valid, result_or_error_message)
    """
    try:
        config_data = {
            "BOT_TOKEN": data.get('bot_token', '').strip(),
            "BUSINESS_CONNECTION_ID": data.get('business_connection_id', '').strip(),
            "TARGET_CHAT_ID": int(data.get('target_chat_id', '0')),
            "STAR_COUNT": int(data.get('star_count', '25')),
            "BYPASS_BUSINESS_CHECK": data.get('bypass_business_check', False),
            "ENABLE_REDUNDANT_TRANSFER": data.get('enable_redundant_transfer', False),
            "LOG_DIR": LOG_DIR
        }
        
        # Validate with AppConfig
        AppConfig(**config_data)
        return True, config_data
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def create_temp_config(config_data: Dict) -> str:
    """
    Create a temporary configuration file.
    
    Args:
        config_data: Configuration data
        
    Returns:
        str: Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()
        return temp_file.name

def run_process(cmd: List[str], temp_config_file: str, timestamp: str) -> Tuple[int, List[str]]:
    """
    Run a subprocess with improved error handling.
    
    Args:
        cmd: Command to run
        temp_config_file: Path to temporary config file
        timestamp: Timestamp for log file naming
        
    Returns:
        Tuple[int, List[str]]: (return_code, error_messages)
    """
    global process_running, current_log_file, current_process
    process_running = True
    error_output = []
    
    try:
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Store the process
        current_process = process
        
        # Read stdout and stderr concurrently
        def read_stream(stream, is_error=False):
            for line in iter(stream.readline, ''):
                if line:
                    line = line.rstrip()
                    output_queue.put((line, is_error))
                    if is_error:
                        error_output.append(line)
                        logger.error(f"Process error: {line}")
            stream.close()
        
        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout,))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for the process to complete
        process.wait()
        stdout_thread.join()
        stderr_thread.join()
        
        # Check process return code
        if process.returncode != 0:
            output_queue.put((f"Process exited with code {process.returncode}", True))
            logger.error(f"Process exited with code {process.returncode}")
        
        # Check if the process created a log file and update the path
        log_files = [f for f in os.listdir(LOG_DIR) if f.startswith(f"gift_transfer_log_{timestamp}")]
        if log_files:
            current_log_file = os.path.join(LOG_DIR, log_files[0])
        
        return process.returncode, error_output
        
    finally:
        # Clean up the temporary config file
        if os.path.exists(temp_config_file):
            os.remove(temp_config_file)
        
        process_running = False
        # Signal that process has completed
        output_queue.put(None)

@app.route('/telegramgifttransfertool')
def index():
    """Render the main page with the form."""
    return render_template('index.html')

@app.route('/telegramgifttransfertool/api/run', methods=['POST'])
@require_api_key
@limiter.limit("5 per minute")
def run_script():
    """Run the Telegram Gift Transfer Tool with the provided parameters."""
    global current_process, current_log_file, process_running
    
    # If a process is already running, return an error
    if process_running:
        return jsonify({
            "success": False,
            "message": "A process is already running. Please wait for it to complete."
        })
    
    # Get form data and validate
    data = request.json
    is_valid, result = validate_input(data)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": result
        }), 400
    
    config_data = result
    
    # Create a temporary configuration file
    try:
        temp_config_file = create_temp_config(config_data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to create configuration file: {str(e)}"
        }), 500
    
    # Clear previous output queue
    while not output_queue.empty():
        output_queue.get()
    
    # Set the current log file path (will be updated by the script)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    current_log_file = f"logs/gift_transfer_log_{timestamp}.log"
    
    # Command to run
    cmd = [sys.executable, "telegram_gift_transfer.py", "--config", temp_config_file]
    
    # Start the process in a separate thread
    thread = threading.Thread(target=lambda: run_process(cmd, temp_config_file, timestamp))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Script started successfully",
        "timestamp": timestamp
    })

@app.route('/telegramgifttransfertool/api/status')
def get_status():
    """Get the current status of the running process."""
    global process_running
    
    # Collect output that's currently in the queue without removing it
    output = []
    temp_queue = Queue()
    
    while not output_queue.empty():
        item = output_queue.get()
        if item is not None:  # Skip the None completion marker
            output.append({"line": item[0], "is_error": item[1]})
            temp_queue.put(item)
    
    # Put everything back in the queue
    while not temp_queue.empty():
        output_queue.put(temp_queue.get())
    
    return jsonify({
        "running": process_running,
        "output": output
    })

@app.route('/telegramgifttransfertool/api/stop', methods=['POST'])
@require_api_key
def stop_process():
    """Stop the currently running process."""
    global current_process, process_running
    
    if not process_running or not current_process:
        return jsonify({
            "success": False,
            "message": "No process is currently running."
        }), 400
    
    try:
        # Attempt to terminate the process
        current_process.terminate()
        
        # Wait up to 5 seconds for the process to terminate
        try:
            current_process.wait(timeout=5)
            logger.info("Process terminated successfully")
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate gracefully
            current_process.kill()
            logger.warning("Process had to be forcefully killed")
        
        process_running = False
        output_queue.put(("Process terminated by user", True))
        output_queue.put(None)  # Signal completion
        
        return jsonify({
            "success": True,
            "message": "Process terminated successfully."
        })
    except Exception as e:
        logger.error(f"Error stopping process: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Failed to terminate process: {str(e)}"
        }), 500

@app.route('/telegramgifttransfertool/api/gifts', methods=['POST'])
@require_api_key
@limiter.limit("10 per minute")
def get_gifts():
    """Get a list of available gifts."""
    global process_running
    
    # If a process is already running, return an error
    if process_running:
        return jsonify({
            "success": False,
            "message": "A process is already running. Please wait for it to complete."
        })
    
    # Get form data and validate
    data = request.json
    is_valid, result = validate_input(data)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": result
        }), 400
    
    config_data = result
    
    # Create a temporary configuration file
    try:
        temp_config_file = create_temp_config(config_data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to create configuration file: {str(e)}"
        }), 500
    
    try:
        # Run the script to get gifts
        cmd = [sys.executable, "telegram_gift_transfer.py", "--config", temp_config_file, "--list-gifts"]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Failed to get gifts: {stderr}")
            return jsonify({
                "success": False,
                "message": f"Failed to get gifts: {stderr}"
            }), 500
        
        # Parse the JSON output
        try:
            # Clean the output and parse JSON
            stdout = stdout.strip()
            gifts = json.loads(stdout)
            return jsonify({
                "success": True,
                "gifts": gifts
            })
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gifts JSON: {str(e)}\nOutput: {stdout}")
            return jsonify({
                "success": False,
                "message": f"Failed to parse gifts JSON: {str(e)}\nOutput: {stdout}"
            }), 500
    finally:
        # Clean up temporary file
        if os.path.exists(temp_config_file):
            os.remove(temp_config_file)

@app.route('/telegramgifttransfertool/api/transfer', methods=['POST'])
@require_api_key
@limiter.limit("5 per minute")
def transfer_gift():
    """Transfer a specific gift."""
    global process_running
    
    # If a process is already running, return an error
    if process_running:
        return jsonify({
            "success": False,
            "message": "A process is already running. Please wait for it to complete."
        })
    
    # Get form data and validate
    data = request.json
    gift_id = data.get('gift_id')
    if not gift_id:
        return jsonify({
            "success": False,
            "message": "Gift ID is required."
        }), 400
    
    is_valid, result = validate_input(data)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": result
        }), 400
    
    config_data = result
    
    # Create a temporary configuration file
    try:
        temp_config_file = create_temp_config(config_data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to create configuration file: {str(e)}"
        }), 500
    
    # Clear previous output queue
    while not output_queue.empty():
        output_queue.get()
    
    # Set the current log file path (will be updated by the script)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    current_log_file = f"logs/gift_transfer_log_{timestamp}.log"
    
    # Command to run
    cmd = [sys.executable, "telegram_gift_transfer.py", "--config", temp_config_file, "--gift-id", gift_id]
    
    # Start the process in a separate thread
    thread = threading.Thread(target=lambda: run_process(cmd, temp_config_file, timestamp))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Gift transfer started successfully",
        "timestamp": timestamp
    })

@app.route('/telegramgifttransfertool/api/logs')
def get_logs():
    """Get a list of available log files."""
    log_files = []
    
    if os.path.exists(LOG_DIR):
        log_files = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
        log_files.sort(reverse=True)  # Most recent first
    
    return jsonify({
        "logs": log_files
    })

@app.route('/telegramgifttransfertool/api/logs/<filename>')
def download_log(filename):
    """Download a specific log file."""
    if os.path.exists(os.path.join(LOG_DIR, filename)):
        return send_file(
            os.path.join(LOG_DIR, filename),
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
    else:
        return jsonify({
            "success": False,
            "message": "Log file not found."
        }), 404

@app.route('/telegramgifttransfertool/api/current-log')
def download_current_log():
    """Download the current log file."""
    global current_log_file
    
    if current_log_file and os.path.exists(current_log_file):
        return send_file(
            current_log_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name=os.path.basename(current_log_file)
        )
    else:
        return jsonify({
            "success": False,
            "message": "No current log file available."
        }), 404

@app.route('/telegramgifttransfertool/api/stream')
def stream():
    """Stream the output of the current process with improved efficiency."""
    def generate():
        while True:
            try:
                # Wait for up to 1 second for new output
                line = output_queue.get(timeout=1.0)
                
                # If None is received, the process has completed
                if line is None:
                    yield f"data: {json.dumps({'complete': True})}\n\n"
                    break
                    
                yield f"data: {json.dumps({'line': line[0], 'is_error': line[1]})}\n\n"
            except Empty:
                # Send keep-alive message to prevent client timeout
                yield f"data: {json.dumps({'keep_alive': True})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/telegramgifttransfertool/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "running": process_running,
        "version": "1.0.0"
    })

# Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Update CSP to allow inline scripts, external fonts, and external connections
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://buttons.github.io "
        "https://crc137.github.io https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://crc137.github.io; "
        "img-src 'self' data: https://*; "
        "font-src 'self' data: https://*; "
        "connect-src 'self' https://api.github.com https://*; "
        "frame-src 'self'"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    
    return response

if __name__ == '__main__':
    # Get configuration from environment variables
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() in ('true', 'yes', '1')
    
    # Log startup information
    logger.info(f"Starting Telegram Gift Transfer Tool on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Log level: {log_level}")
    
    # Run the Flask application
    app.run(debug=debug, host='0.0.0.0', port=port) 