#!/usr/bin/env python3
"""
Bulk Software Installer Web Interface
A web-based interface for managing bulk software installations
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import json
import os
import threading
import time
from pathlib import Path
from bulk_installer import BulkInstaller, OperationMode
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
installer = None
current_operation = None
operation_logs = []

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')

@app.route('/configs')
def configs():
    """Configuration management page."""
    configs_dir = Path('configs')
    config_files = []
    
    if configs_dir.exists():
        for config_file in configs_dir.glob('*.json'):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                config_files.append({
                    'name': config_file.name,
                    'path': str(config_file),
                    'apps_count': len(config),
                    'tags': list(set([tag for app in config if 'tags' in app for tag in app['tags']]))
                })
            except Exception as e:
                config_files.append({
                    'name': config_file.name,
                    'path': str(config_file),
                    'error': str(e)
                })
    
    return render_template('configs.html', configs=config_files)

@app.route('/config/<filename>')
def view_config(filename):
    """View specific configuration file."""
    config_path = Path('configs') / filename
    if not config_path.exists():
        flash(f'Configuration file {filename} not found', 'error')
        return redirect(url_for('configs'))
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return render_template('view_config.html', config=config, filename=filename)
    except Exception as e:
        flash(f'Error reading configuration: {str(e)}', 'error')
        return redirect(url_for('configs'))

@app.route('/api/configs', methods=['GET'])
def api_configs():
    """API endpoint to get available configurations."""
    configs_dir = Path('configs')
    configs = []
    
    if configs_dir.exists():
        for config_file in configs_dir.glob('*.json'):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                configs.append({
                    'name': config_file.name,
                    'path': str(config_file),
                    'apps_count': len(config),
                    'tags': list(set([tag for app in config if 'tags' in app for tag in app['tags']]))
                })
            except Exception as e:
                configs.append({
                    'name': config_file.name,
                    'path': str(config_file),
                    'error': str(e)
                })
    
    return jsonify(configs)

@app.route('/api/install', methods=['POST'])
def api_install():
    """API endpoint to start installation."""
    global installer, current_operation
    
    try:
        data = request.get_json()
        config_file = data.get('config_file', 'apps.json')
        mode = data.get('mode', 'install')
        workers = data.get('workers', 1)
        tags = data.get('tags', [])
        
        # Validate inputs
        if not Path(config_file).exists():
            return jsonify({'error': f'Configuration file {config_file} not found'}), 400
        
        # Start installation in background thread
        def run_installation():
            global installer, current_operation
            try:
                installer = BulkInstaller(config_file)
                current_operation = {
                    'mode': mode,
                    'config_file': config_file,
                    'workers': workers,
                    'tags': tags,
                    'start_time': time.time(),
                    'status': 'running'
                }
                
                operation_mode = OperationMode(mode)
                results = installer.run(operation_mode, workers, tags)
                
                current_operation['status'] = 'completed'
                current_operation['end_time'] = time.time()
                current_operation['results'] = results
                
                socketio.emit('operation_completed', {
                    'status': 'completed',
                    'results': results
                })
                
            except Exception as e:
                current_operation['status'] = 'failed'
                current_operation['error'] = str(e)
                socketio.emit('operation_failed', {
                    'error': str(e)
                })
        
        thread = threading.Thread(target=run_installation)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': 'Installation started',
            'operation_id': id(current_operation) if current_operation else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def api_status():
    """API endpoint to get current operation status."""
    global current_operation
    
    if current_operation:
        return jsonify(current_operation)
    else:
        return jsonify({'status': 'idle'})

@app.route('/api/logs')
def api_logs():
    """API endpoint to get operation logs."""
    global operation_logs
    return jsonify(operation_logs)

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """API endpoint to stop current operation."""
    global current_operation
    
    if current_operation and current_operation['status'] == 'running':
        current_operation['status'] = 'stopping'
        # Note: In a real implementation, you'd need to implement proper cancellation
        return jsonify({'message': 'Stop request sent'})
    else:
        return jsonify({'error': 'No running operation to stop'}), 400

@app.route('/dashboard')
def dashboard():
    """Dashboard with real-time updates."""
    return render_template('dashboard.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'message': 'Connected to Bulk Installer Web Interface'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')

@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client."""
    global current_operation
    emit('status_update', current_operation or {'status': 'idle'})

# Create templates directory and basic templates
def create_templates():
    """Create basic HTML templates."""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    # Index template
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bulk Software Installer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-download"></i> Bulk Software Installer
            </a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/configs">Configurations</a>
                <a class="nav-link" href="/dashboard">Real-time Dashboard</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-play"></i> Start Installation</h5>
                    </div>
                    <div class="card-body">
                        <form id="installForm">
                            <div class="mb-3">
                                <label for="configFile" class="form-label">Configuration File</label>
                                <select class="form-select" id="configFile" name="configFile">
                                    <option value="apps.json">apps.json</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="mode" class="form-label">Operation Mode</label>
                                <select class="form-select" id="mode" name="mode">
                                    <option value="install">Install</option>
                                    <option value="update">Update</option>
                                    <option value="uninstall">Uninstall</option>
                                    <option value="dry-run">Dry Run</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="workers" class="form-label">Parallel Workers</label>
                                <input type="number" class="form-control" id="workers" name="workers" value="1" min="1" max="10">
                            </div>
                            <div class="mb-3">
                                <label for="tags" class="form-label">Filter by Tags (comma-separated)</label>
                                <input type="text" class="form-control" id="tags" name="tags" placeholder="development,gaming,productivity">
                            </div>
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-play"></i> Start Operation
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-info-circle"></i> System Status</h5>
                    </div>
                    <div class="card-body">
                        <div id="systemStatus">
                            <p><strong>Status:</strong> <span id="status">Idle</span></p>
                            <p><strong>Available Configs:</strong> <span id="configCount">0</span></p>
                            <p><strong>Last Operation:</strong> <span id="lastOperation">None</span></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-terminal"></i> Operation Log</h5>
                    </div>
                    <div class="card-body">
                        <div id="logOutput" style="height: 300px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; font-family: monospace;">
                            <p class="text-muted">No operations yet...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        
        socket.on('connected', function(data) {
            console.log('Connected to server');
            updateLog('Connected to Bulk Installer Web Interface');
        });
        
        socket.on('operation_completed', function(data) {
            updateStatus('Completed');
            updateLog('Operation completed successfully');
            updateLastOperation('Completed');
        });
        
        socket.on('operation_failed', function(data) {
            updateStatus('Failed');
            updateLog('Operation failed: ' + data.error);
            updateLastOperation('Failed');
        });
        
        document.getElementById('installForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                config_file: formData.get('configFile'),
                mode: formData.get('mode'),
                workers: parseInt(formData.get('workers')),
                tags: formData.get('tags').split(',').filter(tag => tag.trim())
            };
            
            fetch('/api/install', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    updateLog('Error: ' + data.error);
                } else {
                    updateStatus('Running');
                    updateLog('Operation started: ' + data.message);
                }
            })
            .catch(error => {
                updateLog('Error: ' + error.message);
            });
        });
        
        function updateStatus(status) {
            document.getElementById('status').textContent = status;
        }
        
        function updateLog(message) {
            const logOutput = document.getElementById('logOutput');
            const timestamp = new Date().toLocaleTimeString();
            logOutput.innerHTML += '<p>[' + timestamp + '] ' + message + '</p>';
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
        function updateLastOperation(operation) {
            document.getElementById('lastOperation').textContent = operation;
        }
        
        // Load available configurations
        fetch('/api/configs')
            .then(response => response.json())
            .then(configs => {
                const configSelect = document.getElementById('configFile');
                configSelect.innerHTML = '';
                configs.forEach(config => {
                    const option = document.createElement('option');
                    option.value = config.path;
                    option.textContent = config.name + ' (' + config.apps_count + ' apps)';
                    configSelect.appendChild(option);
                });
                document.getElementById('configCount').textContent = configs.length;
            });
    </script>
</body>
</html>'''
    
    with open(templates_dir / 'index.html', 'w') as f:
        f.write(index_html)
    
    # Configs template
    configs_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configurations - Bulk Software Installer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-download"></i> Bulk Software Installer
            </a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link active" href="/configs">Configurations</a>
                <a class="nav-link" href="/dashboard">Real-time Dashboard</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h2><i class="fas fa-cogs"></i> Configuration Files</h2>
        
        <div class="row" id="configsList">
            <!-- Configurations will be loaded here -->
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        fetch('/api/configs')
            .then(response => response.json())
            .then(configs => {
                const configsList = document.getElementById('configsList');
                configs.forEach(config => {
                    const configCard = document.createElement('div');
                    configCard.className = 'col-md-6 col-lg-4 mb-4';
                    configCard.innerHTML = `
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">${config.name}</h5>
                                <p class="card-text">
                                    <strong>Apps:</strong> ${config.apps_count}<br>
                                    <strong>Tags:</strong> ${config.tags ? config.tags.join(', ') : 'None'}
                                </p>
                                <a href="/config/${config.name}" class="btn btn-primary btn-sm">
                                    <i class="fas fa-eye"></i> View
                                </a>
                            </div>
                        </div>
                    `;
                    configsList.appendChild(configCard);
                });
            });
    </script>
</body>
</html>'''
    
    with open(templates_dir / 'configs.html', 'w') as f:
        f.write(configs_html)

if __name__ == '__main__':
    # Create templates
    create_templates()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the web interface
    print("Starting Bulk Software Installer Web Interface...")
    print("Access the web interface at: http://localhost:8080")
    
    socketio.run(app, host='0.0.0.0', port=8080, debug=True) 