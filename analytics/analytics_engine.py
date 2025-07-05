#!/usr/bin/env python3
"""
Analytics and Reporting Engine for Bulk Software Installer
Provides real-time metrics, custom reports, and performance analytics
"""

import json
import time
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging
from pathlib import Path
import threading
from collections import defaultdict, Counter
import hashlib
import uuid

@dataclass
class InstallationMetrics:
    """Installation performance metrics."""
    app_name: str
    manager: str
    platform: str
    start_time: datetime
    end_time: datetime
    duration: float
    success: bool
    error_message: Optional[str] = None
    package_size: Optional[int] = None
    download_speed: Optional[float] = None
    system_resources: Optional[Dict] = None

@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_processes: int

@dataclass
class UserMetrics:
    """User interaction metrics."""
    user_id: str
    action: str
    timestamp: datetime
    config_file: str
    tags_used: List[str]
    workers_used: int
    success: bool

class AnalyticsEngine:
    """Main analytics engine for collecting and analyzing data."""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.report_dir = Path("reports")
        self.report_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Metrics storage
        self.installation_metrics: List[InstallationMetrics] = []
        self.system_metrics: List[SystemMetrics] = []
        self.user_metrics: List[UserMetrics] = []
        
        # Real-time counters
        self.real_time_stats = {
            'total_installations': 0,
            'successful_installations': 0,
            'failed_installations': 0,
            'active_operations': 0,
            'total_duration': 0.0,
            'package_managers_used': Counter(),
            'platforms_used': Counter(),
            'tags_used': Counter()
        }
        
        # Thread lock for thread safety
        self.lock = threading.Lock()
        
        # Start background monitoring
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._background_monitoring, daemon=True)
        self.monitor_thread.start()
    
    def _init_database(self):
        """Initialize SQLite database for analytics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS installation_metrics (
                    id TEXT PRIMARY KEY,
                    app_name TEXT,
                    manager TEXT,
                    platform TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration REAL,
                    success BOOLEAN,
                    error_message TEXT,
                    package_size INTEGER,
                    download_speed REAL,
                    system_resources TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    cpu_usage REAL,
                    memory_usage REAL,
                    disk_usage REAL,
                    network_io TEXT,
                    active_processes INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_metrics (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    action TEXT,
                    timestamp TEXT,
                    config_file TEXT,
                    tags_used TEXT,
                    workers_used INTEGER,
                    success BOOLEAN
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS package_analytics (
                    id TEXT PRIMARY KEY,
                    package_name TEXT,
                    install_count INTEGER,
                    success_rate REAL,
                    avg_duration REAL,
                    last_installed TEXT,
                    popularity_score REAL
                )
            ''')
            
            conn.commit()
    
    def record_installation(self, metrics: InstallationMetrics):
        """Record installation metrics."""
        with self.lock:
            self.installation_metrics.append(metrics)
            
            # Update real-time stats
            self.real_time_stats['total_installations'] += 1
            if metrics.success:
                self.real_time_stats['successful_installations'] += 1
            else:
                self.real_time_stats['failed_installations'] += 1
            
            self.real_time_stats['total_duration'] += metrics.duration
            self.real_time_stats['package_managers_used'][metrics.manager] += 1
            self.real_time_stats['platforms_used'][metrics.platform] += 1
            
            # Store in database
            self._store_installation_metrics(metrics)
    
    def record_system_metrics(self, metrics: SystemMetrics):
        """Record system performance metrics."""
        with self.lock:
            self.system_metrics.append(metrics)
            self._store_system_metrics(metrics)
    
    def record_user_action(self, metrics: UserMetrics):
        """Record user interaction metrics."""
        with self.lock:
            self.user_metrics.append(metrics)
            
            # Update tag usage
            for tag in metrics.tags_used:
                self.real_time_stats['tags_used'][tag] += 1
            
            self._store_user_metrics(metrics)
    
    def _store_installation_metrics(self, metrics: InstallationMetrics):
        """Store installation metrics in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO installation_metrics 
                    (id, app_name, manager, platform, start_time, end_time, duration, 
                     success, error_message, package_size, download_speed, system_resources)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    metrics.app_name,
                    metrics.manager,
                    metrics.platform,
                    metrics.start_time.isoformat(),
                    metrics.end_time.isoformat(),
                    metrics.duration,
                    metrics.success,
                    metrics.error_message,
                    metrics.package_size,
                    metrics.download_speed,
                    json.dumps(metrics.system_resources) if metrics.system_resources else None
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store installation metrics: {e}")
    
    def _store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO system_metrics 
                    (id, timestamp, cpu_usage, memory_usage, disk_usage, network_io, active_processes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    metrics.timestamp.isoformat(),
                    metrics.cpu_usage,
                    metrics.memory_usage,
                    metrics.disk_usage,
                    json.dumps(metrics.network_io),
                    metrics.active_processes
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store system metrics: {e}")
    
    def _store_user_metrics(self, metrics: UserMetrics):
        """Store user metrics in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO user_metrics 
                    (id, user_id, action, timestamp, config_file, tags_used, workers_used, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    metrics.user_id,
                    metrics.action,
                    metrics.timestamp.isoformat(),
                    metrics.config_file,
                    json.dumps(metrics.tags_used),
                    metrics.workers_used,
                    metrics.success
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store user metrics: {e}")
    
    def _background_monitoring(self):
        """Background thread for continuous system monitoring."""
        import psutil
        
        while self.monitoring_active:
            try:
                # Collect system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                system_metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_usage=cpu_usage,
                    memory_usage=memory.percent,
                    disk_usage=disk.percent,
                    network_io={
                        'bytes_sent': network.bytes_sent,
                        'bytes_recv': network.bytes_recv,
                        'packets_sent': network.packets_sent,
                        'packets_recv': network.packets_recv
                    },
                    active_processes=len(psutil.pids())
                )
                
                self.record_system_metrics(system_metrics)
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in background monitoring: {e}")
                time.sleep(60)
    
    def get_real_time_stats(self) -> Dict:
        """Get real-time statistics."""
        with self.lock:
            stats = self.real_time_stats.copy()
            
            # Calculate success rate
            if stats['total_installations'] > 0:
                stats['success_rate'] = (stats['successful_installations'] / stats['total_installations']) * 100
            else:
                stats['success_rate'] = 0.0
            
            # Calculate average duration
            if stats['total_installations'] > 0:
                stats['avg_duration'] = stats['total_duration'] / stats['total_installations']
            else:
                stats['avg_duration'] = 0.0
            
            return stats
    
    def generate_installation_report(self, start_date: Optional[datetime] = None, 
                                   end_date: Optional[datetime] = None) -> Dict:
        """Generate comprehensive installation report."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get installation data
            df = pd.read_sql_query('''
                SELECT * FROM installation_metrics 
                WHERE start_time BETWEEN ? AND ?
            ''', conn, params=[start_date.isoformat(), end_date.isoformat()])
        
        if df.empty:
            return {"message": "No data found for the specified period"}
        
        # Convert timestamps
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        
        # Calculate metrics
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_installations': len(df),
                'successful_installations': len(df[df['success'] == True]),
                'failed_installations': len(df[df['success'] == False]),
                'success_rate': (len(df[df['success'] == True]) / len(df)) * 100,
                'avg_duration': df['duration'].mean(),
                'total_duration': df['duration'].sum()
            },
            'by_package_manager': df.groupby('manager').agg({
                'success': 'count',
                'duration': ['mean', 'sum']
            }).to_dict(),
            'by_platform': df.groupby('platform').agg({
                'success': 'count',
                'duration': ['mean', 'sum']
            }).to_dict(),
            'top_apps': df.groupby('app_name').agg({
                'success': 'count',
                'duration': 'mean'
            }).sort_values('success', ascending=False).head(10).to_dict(),
            'error_analysis': df[df['success'] == False]['error_message'].value_counts().head(10).to_dict()
        }
        
        return report
    
    def generate_performance_report(self) -> Dict:
        """Generate system performance report."""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('''
                SELECT * FROM system_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1000
            ''', conn)
        
        if df.empty:
            return {"message": "No system metrics data available"}
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        report = {
            'system_performance': {
                'avg_cpu_usage': df['cpu_usage'].mean(),
                'max_cpu_usage': df['cpu_usage'].max(),
                'avg_memory_usage': df['memory_usage'].mean(),
                'max_memory_usage': df['memory_usage'].max(),
                'avg_disk_usage': df['disk_usage'].mean(),
                'max_disk_usage': df['disk_usage'].max()
            },
            'trends': {
                'cpu_trend': df.groupby(df['timestamp'].dt.hour)['cpu_usage'].mean().to_dict(),
                'memory_trend': df.groupby(df['timestamp'].dt.hour)['memory_usage'].mean().to_dict()
            }
        }
        
        return report
    
    def generate_user_activity_report(self) -> Dict:
        """Generate user activity report."""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('''
                SELECT * FROM user_metrics 
                ORDER BY timestamp DESC
            ''', conn)
        
        if df.empty:
            return {"message": "No user activity data available"}
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['tags_used'] = df['tags_used'].apply(json.loads)
        
        report = {
            'user_activity': {
                'total_actions': len(df),
                'unique_users': df['user_id'].nunique(),
                'success_rate': (len(df[df['success'] == True]) / len(df)) * 100
            },
            'popular_actions': df['action'].value_counts().to_dict(),
            'popular_configs': df['config_file'].value_counts().to_dict(),
            'popular_tags': dict(Counter([tag for tags in df['tags_used'] for tag in tags]).most_common(10)),
            'worker_usage': df['workers_used'].value_counts().to_dict()
        }
        
        return report
    
    def create_visualization_report(self, output_path: str = "reports/analytics_report.html"):
        """Create an HTML report with visualizations."""
        # Get data
        installation_report = self.generate_installation_report()
        performance_report = self.generate_performance_report()
        user_report = self.generate_user_activity_report()
        
        # Create visualizations
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Installation success rate pie chart
        if 'summary' in installation_report:
            success_data = [installation_report['summary']['successful_installations'], 
                          installation_report['summary']['failed_installations']]
            axes[0, 0].pie(success_data, labels=['Success', 'Failed'], autopct='%1.1f%%')
            axes[0, 0].set_title('Installation Success Rate')
        
        # Package manager usage
        if 'by_package_manager' in installation_report:
            managers = list(installation_report['by_package_manager'].keys())
            counts = []
            for m in managers:
                manager_data = installation_report['by_package_manager'][m]
                if 'success' in manager_data and 'count' in manager_data['success']:
                    counts.append(int(manager_data['success']['count']))
                else:
                    counts.append(0)
            if counts and managers:
                # Convert to strings to avoid numpy array issues
                manager_labels = [str(m) for m in managers]
                axes[0, 1].bar(manager_labels, counts)
                axes[0, 1].set_title('Usage by Package Manager')
                axes[0, 1].tick_params(axis='x', rotation=45)
        
        # Performance trends
        if 'trends' in performance_report and 'cpu_trend' in performance_report['trends']:
            hours = list(performance_report['trends']['cpu_trend'].keys())
            cpu_values = list(performance_report['trends']['cpu_trend'].values())
            if hours and cpu_values:
                # Convert to proper types
                hour_labels = [str(h) for h in hours]
                cpu_nums = [float(v) for v in cpu_values]
                axes[1, 0].plot(hour_labels, cpu_nums, marker='o')
                axes[1, 0].set_title('CPU Usage by Hour')
                axes[1, 0].set_xlabel('Hour of Day')
                axes[1, 0].set_ylabel('CPU Usage (%)')
        
        # User activity
        if 'popular_actions' in user_report:
            actions = list(user_report['popular_actions'].keys())[:5]
            counts = list(user_report['popular_actions'].values())[:5]
            axes[1, 1].barh(actions, counts)
            axes[1, 1].set_title('Most Popular User Actions')
        
        plt.tight_layout()
        
        # Save plot
        plot_path = "reports/analytics_plot.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        
        # Create HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bulk Installer Analytics Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e8f4f8; border-radius: 3px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Bulk Software Installer Analytics Report</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="section">
                <h2>Installation Summary</h2>
                <div class="metric">
                    <strong>Total Installations:</strong> {installation_report.get('summary', {}).get('total_installations', 0)}
                </div>
                <div class="metric">
                    <strong>Success Rate:</strong> {installation_report.get('summary', {}).get('success_rate', 0):.1f}%
                </div>
                <div class="metric">
                    <strong>Average Duration:</strong> {installation_report.get('summary', {}).get('avg_duration', 0):.2f}s
                </div>
            </div>
            
            <div class="section">
                <h2>Visualizations</h2>
                <img src="analytics_plot.png" alt="Analytics Charts" style="max-width: 100%;">
            </div>
            
            <div class="section">
                <h2>User Activity</h2>
                <div class="metric">
                    <strong>Total Actions:</strong> {user_report.get('user_activity', {}).get('total_actions', 0)}
                </div>
                <div class="metric">
                    <strong>Unique Users:</strong> {user_report.get('user_activity', {}).get('unique_users', 0)}
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return output_path
    
    def export_data(self, format: str = 'json', output_path: str = None) -> str:
        """Export analytics data in various formats."""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"reports/analytics_export_{timestamp}.{format}"
        
        # Collect all data
        data = {
            'installation_metrics': [asdict(m) for m in self.installation_metrics],
            'system_metrics': [asdict(m) for m in self.system_metrics],
            'user_metrics': [asdict(m) for m in self.user_metrics],
            'real_time_stats': self.get_real_time_stats(),
            'reports': {
                'installation': self.generate_installation_report(),
                'performance': self.generate_performance_report(),
                'user_activity': self.generate_user_activity_report()
            }
        }
        
        if format == 'json':
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        elif format == 'csv':
            # Export each metric type to separate CSV files
            for metric_type, metrics in data.items():
                if isinstance(metrics, list) and metrics:
                    df = pd.DataFrame(metrics)
                    csv_path = output_path.replace('.csv', f'_{metric_type}.csv')
                    df.to_csv(csv_path, index=False)
        
        return output_path
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old analytics data."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM installation_metrics 
                WHERE start_time < ?
            ''', [cutoff_date.isoformat()])
            
            conn.execute('''
                DELETE FROM system_metrics 
                WHERE timestamp < ?
            ''', [cutoff_date.isoformat()])
            
            conn.execute('''
                DELETE FROM user_metrics 
                WHERE timestamp < ?
            ''', [cutoff_date.isoformat()])
            
            conn.commit()
        
        self.logger.info(f"Cleaned up data older than {days_to_keep} days")

# Global analytics instance
analytics_engine = AnalyticsEngine() 