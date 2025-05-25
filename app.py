import os
import sys
import json
import time
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context

app = Flask(__name__)

# Configuration
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Global variables to store process information
current_process = None
current_log_file = None
process_output = []
process_running = False

@app.route('/telegramgifttransfertool')
def index():
    """Render the main page with the form."""
    return render_template('index.html')

@app.route('/telegramgifttransfertool/api/run', methods=['POST'])
def run_script():
    """Run the Telegram Gift Transfer Tool with the provided parameters."""
    global current_process, current_log_file, process_output, process_running
    
    # If a process is already running, return an error
    if process_running:
        return jsonify({
            "success": False,
            "message": "A process is already running. Please wait for it to complete."
        })
    
    # Get form data
    data = request.json
    bot_token = data.get('bot_token', '')
    business_connection_id = data.get('business_connection_id', '')
    target_chat_id = data.get('target_chat_id', '')
    star_count = data.get('star_count', '25')
    
    # Validate required fields
    if not bot_token or not business_connection_id or not target_chat_id:
        return jsonify({
            "success": False,
            "message": "Please fill in all required fields."
        })
    
    # Create a temporary configuration file
    config_data = {
        "BOT_TOKEN": bot_token,
        "BUSINESS_CONNECTION_ID": business_connection_id,
        "TARGET_CHAT_ID": int(target_chat_id),
        "STAR_COUNT": int(star_count)
    }
    
    # Create a timestamp for this run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_config_file = f"temp_config_{timestamp}.json"
    
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)
    
    # Clear previous output
    process_output = []
    
    # Set the current log file path (will be updated by the script)
    current_log_file = f"logs/gift_transfer_log_{timestamp}.log"
    
    # Function to run in a separate thread
    def run_process():
        global process_running, process_output, current_log_file
        
        process_running = True
        try:
            # Run the script with the temporary config file
            cmd = [sys.executable, "telegram_gift_transfer.py", "--config", temp_config_file]
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Store the process
            current_process = process
            
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    process_output.append(line.rstrip())
            
            # Wait for the process to complete
            process.wait()
            
            # Check if the process created a log file and update the path
            log_files = [f for f in os.listdir(LOG_DIR) if f.startswith(f"gift_transfer_log_{timestamp}")]
            if log_files:
                current_log_file = os.path.join(LOG_DIR, log_files[0])
            
        finally:
            # Clean up the temporary config file
            if os.path.exists(temp_config_file):
                os.remove(temp_config_file)
            
            process_running = False
    
    # Start the process in a separate thread
    thread = threading.Thread(target=run_process)
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
    global process_running, process_output
    
    return jsonify({
        "running": process_running,
        "output": process_output
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
    """Stream the output of the current process."""
    def generate():
        global process_output
        last_index = 0
        
        while True:
            if last_index < len(process_output):
                new_output = process_output[last_index:]
                last_index = len(process_output)
                
                for line in new_output:
                    yield f"data: {json.dumps({'line': line})}\n\n"
            
            time.sleep(0.5)
            
            # If the process is no longer running, send a completion event
            if not process_running and last_index >= len(process_output):
                yield f"data: {json.dumps({'complete': True})}\n\n"
                break
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    # Get port from environment variable for production deployment
    port = int(os.environ.get('PORT', 3002))
    app.run(debug=False, host='0.0.0.0', port=port) 
