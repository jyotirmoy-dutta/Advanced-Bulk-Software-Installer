#!/usr/bin/env python3
"""
Network and Distribution Management System
Provides peer-to-peer distribution, bandwidth optimization, and mirror management
"""

import asyncio
import aiohttp
import aiofiles
import hashlib
import json
import logging
import os
import time
import threading
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import uuid
from enum import Enum
import socket
import struct
import select
import queue
import concurrent.futures
from collections import defaultdict, deque
import ssl
import tempfile
import shutil

class DistributionMode(Enum):
    CENTRALIZED = "centralized"
    P2P = "p2p"
    HYBRID = "hybrid"

class MirrorStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SLOW = "slow"
    ERROR = "error"

@dataclass
class Mirror:
    """Represents a distribution mirror."""
    id: str
    name: str
    url: str
    location: str
    bandwidth: int  # Mbps
    status: MirrorStatus
    last_check: float
    success_rate: float
    response_time: float
    supported_managers: List[str]
    priority: int
    max_connections: int
    current_connections: int = 0

@dataclass
class PackageInfo:
    """Represents package distribution information."""
    name: str
    manager: str
    version: str
    size: int
    checksum: str
    mirrors: List[str]
    chunks: List[str]
    chunk_size: int
    total_chunks: int

@dataclass
class PeerNode:
    """Represents a peer node in P2P network."""
    id: str
    address: str
    port: int
    capabilities: List[str]
    shared_packages: List[str]
    bandwidth: int
    last_seen: float
    is_trusted: bool
    reputation: float

class BandwidthManager:
    """Manages bandwidth allocation and optimization."""
    
    def __init__(self, max_bandwidth: int = 100):  # Mbps
        self.max_bandwidth = max_bandwidth
        self.current_usage = 0
        self.connections: Dict[str, int] = {}
        self.lock = threading.Lock()
        
        # Bandwidth allocation strategies
        self.strategies = {
            'fair': self._fair_allocation,
            'priority': self._priority_allocation,
            'adaptive': self._adaptive_allocation
        }
    
    def allocate_bandwidth(self, connection_id: str, requested: int, 
                          strategy: str = 'fair', priority: int = 1) -> int:
        """Allocate bandwidth for a connection."""
        with self.lock:
            if strategy in self.strategies:
                allocated = self.strategies[strategy](connection_id, requested, priority)
            else:
                allocated = self._fair_allocation(connection_id, requested, priority)
            
            self.connections[connection_id] = allocated
            self.current_usage += allocated
            
            return allocated
    
    def release_bandwidth(self, connection_id: str):
        """Release allocated bandwidth."""
        with self.lock:
            if connection_id in self.connections:
                self.current_usage -= self.connections[connection_id]
                del self.connections[connection_id]
    
    def _fair_allocation(self, connection_id: str, requested: int, priority: int) -> int:
        """Fair bandwidth allocation."""
        available = self.max_bandwidth - self.current_usage
        if available <= 0:
            return 0
        
        # Simple fair allocation
        allocated = min(requested, available // max(1, len(self.connections) + 1))
        return allocated
    
    def _priority_allocation(self, connection_id: str, requested: int, priority: int) -> int:
        """Priority-based bandwidth allocation."""
        available = self.max_bandwidth - self.current_usage
        if available <= 0:
            return 0
        
        # Priority-based allocation
        allocated = min(requested, available * priority // 10)
        return allocated
    
    def _adaptive_allocation(self, connection_id: str, requested: int, priority: int) -> int:
        """Adaptive bandwidth allocation based on network conditions."""
        available = self.max_bandwidth - self.current_usage
        if available <= 0:
            return 0
        
        # Adaptive allocation based on current usage
        usage_ratio = self.current_usage / self.max_bandwidth
        if usage_ratio > 0.8:
            # High usage - reduce allocation
            allocated = min(requested, available // 4)
        elif usage_ratio > 0.5:
            # Medium usage - moderate allocation
            allocated = min(requested, available // 2)
        else:
            # Low usage - generous allocation
            allocated = min(requested, available)
        
        return allocated
    
    def get_usage_stats(self) -> Dict:
        """Get bandwidth usage statistics."""
        with self.lock:
            return {
                'max_bandwidth': self.max_bandwidth,
                'current_usage': self.current_usage,
                'available': self.max_bandwidth - self.current_usage,
                'usage_percentage': (self.current_usage / self.max_bandwidth) * 100,
                'active_connections': len(self.connections),
                'connections': self.connections.copy()
            }

class MirrorManager:
    """Manages distribution mirrors and their health."""
    
    def __init__(self, db_path: str = "mirrors.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.mirrors: Dict[str, Mirror] = {}
        self.health_check_interval = 300  # 5 minutes
        self.lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # Load mirrors
        self._load_mirrors()
        
        # Start health monitoring
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._health_monitoring, daemon=True)
        self.monitor_thread.start()
    
    def _init_database(self):
        """Initialize mirror database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mirrors (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    url TEXT,
                    location TEXT,
                    bandwidth INTEGER,
                    status TEXT,
                    last_check REAL,
                    success_rate REAL,
                    response_time REAL,
                    supported_managers TEXT,
                    priority INTEGER,
                    max_connections INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mirror_health_log (
                    id TEXT PRIMARY KEY,
                    mirror_id TEXT,
                    timestamp REAL,
                    status TEXT,
                    response_time REAL,
                    success BOOLEAN
                )
            ''')
            
            conn.commit()
    
    def _load_mirrors(self):
        """Load mirrors from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM mirrors')
            for row in cursor.fetchall():
                mirror = Mirror(
                    id=row[0],
                    name=row[1],
                    url=row[2],
                    location=row[3],
                    bandwidth=row[4],
                    status=MirrorStatus(row[5]),
                    last_check=row[6],
                    success_rate=row[7],
                    response_time=row[8],
                    supported_managers=json.loads(row[9]),
                    priority=row[10],
                    max_connections=row[11]
                )
                self.mirrors[mirror.id] = mirror
    
    def add_mirror(self, name: str, url: str, location: str, bandwidth: int,
                   supported_managers: List[str], priority: int = 1,
                   max_connections: int = 10) -> str:
        """Add a new mirror."""
        mirror_id = str(uuid.uuid4())
        
        mirror = Mirror(
            id=mirror_id,
            name=name,
            url=url,
            location=location,
            bandwidth=bandwidth,
            status=MirrorStatus.OFFLINE,
            last_check=time.time(),
            success_rate=0.0,
            response_time=0.0,
            supported_managers=supported_managers,
            priority=priority,
            max_connections=max_connections
        )
        
        with self.lock:
            self.mirrors[mirror_id] = mirror
            self._save_mirror(mirror)
        
        return mirror_id
    
    def remove_mirror(self, mirror_id: str) -> bool:
        """Remove a mirror."""
        with self.lock:
            if mirror_id in self.mirrors:
                del self.mirrors[mirror_id]
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('DELETE FROM mirrors WHERE id = ?', [mirror_id])
                    conn.commit()
                
                return True
            return False
    
    def get_best_mirrors(self, manager: str, count: int = 3) -> List[Mirror]:
        """Get the best mirrors for a specific package manager."""
        with self.lock:
            suitable_mirrors = [
                mirror for mirror in self.mirrors.values()
                if manager in mirror.supported_managers and 
                mirror.status == MirrorStatus.ONLINE and
                mirror.current_connections < mirror.max_connections
            ]
            
            # Sort by priority, success rate, and response time
            suitable_mirrors.sort(
                key=lambda m: (m.priority, m.success_rate, -m.response_time),
                reverse=True
            )
            
            return suitable_mirrors[:count]
    
    def update_mirror_status(self, mirror_id: str, status: MirrorStatus,
                           response_time: float = None, success: bool = None):
        """Update mirror status and health metrics."""
        with self.lock:
            if mirror_id not in self.mirrors:
                return
            
            mirror = self.mirrors[mirror_id]
            mirror.status = status
            mirror.last_check = time.time()
            
            if response_time is not None:
                mirror.response_time = response_time
            
            if success is not None:
                # Update success rate (simple moving average)
                if mirror.success_rate == 0.0:
                    mirror.success_rate = 1.0 if success else 0.0
                else:
                    mirror.success_rate = mirror.success_rate * 0.9 + (1.0 if success else 0.0) * 0.1
            
            self._save_mirror(mirror)
            self._log_health_check(mirror_id, status, response_time, success)
    
    def _health_monitoring(self):
        """Background health monitoring for mirrors."""
        while self.monitoring_active:
            try:
                for mirror in self.mirrors.values():
                    if time.time() - mirror.last_check > self.health_check_interval:
                        self._check_mirror_health(mirror)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in health monitoring: {e}")
                time.sleep(300)
    
    async def _check_mirror_health(self, mirror: Mirror):
        """Check health of a specific mirror."""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{mirror.url}/health", timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        self.update_mirror_status(
                            mirror.id, MirrorStatus.ONLINE, response_time, True
                        )
                    else:
                        self.update_mirror_status(
                            mirror.id, MirrorStatus.ERROR, response_time, False
                        )
                        
        except asyncio.TimeoutError:
            self.update_mirror_status(
                mirror.id, MirrorStatus.SLOW, 10.0, False
            )
        except Exception as e:
            self.update_mirror_status(
                mirror.id, MirrorStatus.OFFLINE, 0.0, False
            )
    
    def _save_mirror(self, mirror: Mirror):
        """Save mirror to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO mirrors 
                (id, name, url, location, bandwidth, status, last_check,
                 success_rate, response_time, supported_managers, priority, max_connections)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                mirror.id, mirror.name, mirror.url, mirror.location,
                mirror.bandwidth, mirror.status.value, mirror.last_check,
                mirror.success_rate, mirror.response_time,
                json.dumps(mirror.supported_managers), mirror.priority,
                mirror.max_connections
            ))
            conn.commit()
    
    def _log_health_check(self, mirror_id: str, status: MirrorStatus,
                         response_time: float, success: bool):
        """Log health check result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO mirror_health_log 
                (id, mirror_id, timestamp, status, response_time, success)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), mirror_id, time.time(),
                status.value, response_time, success
            ))
            conn.commit()

class P2PDistributionManager:
    """Peer-to-peer distribution manager."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.logger = logging.getLogger(__name__)
        self.peers: Dict[str, PeerNode] = {}
        self.shared_packages: Dict[str, Set[str]] = defaultdict(set)
        self.download_queue = queue.Queue()
        self.upload_queue = queue.Queue()
        
        # Network settings
        self.max_peers = 50
        self.peer_timeout = 300  # 5 minutes
        self.chunk_size = 1024 * 1024  # 1MB chunks
        
        # Start P2P server
        self.server_running = False
        self.server_thread = threading.Thread(target=self._start_server, daemon=True)
        self.server_thread.start()
        
        # Start background tasks
        self.background_tasks = []
        self._start_background_tasks()
    
    def _start_server(self):
        """Start P2P server."""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(10)
            
            self.server_running = True
            self.logger.info(f"P2P server started on port {self.port}")
            
            while self.server_running:
                try:
                    client_socket, address = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self._handle_client, args=(client_socket, address)
                    )
                    client_thread.start()
                except Exception as e:
                    if self.server_running:
                        self.logger.error(f"Error accepting client: {e}")
            
            server_socket.close()
            
        except Exception as e:
            self.logger.error(f"Failed to start P2P server: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle incoming P2P client connection."""
        try:
            # Receive handshake
            data = client_socket.recv(1024)
            if not data:
                return
            
            message = json.loads(data.decode())
            
            if message['type'] == 'handshake':
                # Register peer
                peer_id = message['peer_id']
                peer = PeerNode(
                    id=peer_id,
                    address=address[0],
                    port=message['port'],
                    capabilities=message['capabilities'],
                    shared_packages=message['shared_packages'],
                    bandwidth=message['bandwidth'],
                    last_seen=time.time(),
                    is_trusted=message.get('trusted', False),
                    reputation=message.get('reputation', 0.5)
                )
                
                self.peers[peer_id] = peer
                
                # Update shared packages
                for package in peer.shared_packages:
                    self.shared_packages[package].add(peer_id)
                
                # Send response
                response = {
                    'type': 'handshake_response',
                    'peer_id': str(uuid.uuid4()),
                    'capabilities': ['download', 'upload'],
                    'shared_packages': list(self.shared_packages.keys())
                }
                client_socket.send(json.dumps(response).encode())
                
                # Handle subsequent messages
                self._handle_peer_messages(client_socket, peer_id)
                
        except Exception as e:
            self.logger.error(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
    
    def _handle_peer_messages(self, client_socket: socket.socket, peer_id: str):
        """Handle messages from a peer."""
        while self.server_running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                message = json.loads(data.decode())
                
                if message['type'] == 'download_request':
                    self._handle_download_request(client_socket, message, peer_id)
                elif message['type'] == 'upload_offer':
                    self._handle_upload_offer(client_socket, message, peer_id)
                elif message['type'] == 'chunk_request':
                    self._handle_chunk_request(client_socket, message, peer_id)
                elif message['type'] == 'ping':
                    client_socket.send(json.dumps({'type': 'pong'}).encode())
                
            except Exception as e:
                self.logger.error(f"Error handling peer message: {e}")
                break
    
    def _handle_download_request(self, client_socket: socket.socket, message: Dict, peer_id: str):
        """Handle download request from peer."""
        package_name = message['package']
        
        if package_name in self.shared_packages:
            # We have this package
            response = {
                'type': 'download_response',
                'package': package_name,
                'available': True,
                'chunks': self._get_package_chunks(package_name)
            }
        else:
            response = {
                'type': 'download_response',
                'package': package_name,
                'available': False
            }
        
        client_socket.send(json.dumps(response).encode())
    
    def _handle_upload_offer(self, client_socket: socket.socket, message: Dict, peer_id: str):
        """Handle upload offer from peer."""
        package_name = message['package']
        
        # Add to shared packages
        self.shared_packages[package_name].add(peer_id)
        
        response = {
            'type': 'upload_response',
            'package': package_name,
            'accepted': True
        }
        
        client_socket.send(json.dumps(response).encode())
    
    def _handle_chunk_request(self, client_socket: socket.socket, message: Dict, peer_id: str):
        """Handle chunk request from peer."""
        package_name = message['package']
        chunk_id = message['chunk_id']
        
        try:
            chunk_data = self._get_package_chunk(package_name, chunk_id)
            response = {
                'type': 'chunk_response',
                'package': package_name,
                'chunk_id': chunk_id,
                'data': chunk_data.hex() if chunk_data else None
            }
        except Exception as e:
            response = {
                'type': 'chunk_response',
                'package': package_name,
                'chunk_id': chunk_id,
                'error': str(e)
            }
        
        client_socket.send(json.dumps(response).encode())
    
    def _get_package_chunks(self, package_name: str) -> List[str]:
        """Get list of chunks for a package."""
        # This would typically read from a package index
        # For now, return dummy chunks
        return [f"{package_name}_chunk_{i}" for i in range(10)]
    
    def _get_package_chunk(self, package_name: str, chunk_id: str) -> bytes:
        """Get a specific chunk of a package."""
        # This would typically read from disk
        # For now, return dummy data
        return b"dummy_chunk_data"
    
    def _start_background_tasks(self):
        """Start background P2P tasks."""
        # Peer discovery
        discovery_task = threading.Thread(target=self._peer_discovery, daemon=True)
        discovery_task.start()
        self.background_tasks.append(discovery_task)
        
        # Peer cleanup
        cleanup_task = threading.Thread(target=self._peer_cleanup, daemon=True)
        cleanup_task.start()
        self.background_tasks.append(cleanup_task)
    
    def _peer_discovery(self):
        """Discover new peers on the network."""
        while self.server_running:
            try:
                # Simple peer discovery using broadcast
                # In a real implementation, this would use more sophisticated methods
                time.sleep(60)
            except Exception as e:
                self.logger.error(f"Error in peer discovery: {e}")
                time.sleep(300)
    
    def _peer_cleanup(self):
        """Clean up inactive peers."""
        while self.server_running:
            try:
                current_time = time.time()
                inactive_peers = []
                
                for peer_id, peer in self.peers.items():
                    if current_time - peer.last_seen > self.peer_timeout:
                        inactive_peers.append(peer_id)
                
                for peer_id in inactive_peers:
                    self._remove_peer(peer_id)
                
                time.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error in peer cleanup: {e}")
                time.sleep(300)
    
    def _remove_peer(self, peer_id: str):
        """Remove an inactive peer."""
        if peer_id in self.peers:
            peer = self.peers[peer_id]
            
            # Remove from shared packages
            for package in peer.shared_packages:
                if peer_id in self.shared_packages[package]:
                    self.shared_packages[package].remove(peer_id)
            
            del self.peers[peer_id]
    
    def connect_to_peer(self, address: str, port: int) -> bool:
        """Connect to a peer node."""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((address, port))
            
            # Send handshake
            handshake = {
                'type': 'handshake',
                'peer_id': str(uuid.uuid4()),
                'port': self.port,
                'capabilities': ['download', 'upload'],
                'shared_packages': list(self.shared_packages.keys()),
                'bandwidth': 100,  # Mbps
                'trusted': False,
                'reputation': 0.5
            }
            
            client_socket.send(json.dumps(handshake).encode())
            
            # Receive response
            data = client_socket.recv(1024)
            response = json.loads(data.decode())
            
            if response['type'] == 'handshake_response':
                # Register the peer
                peer = PeerNode(
                    id=response['peer_id'],
                    address=address,
                    port=port,
                    capabilities=response['capabilities'],
                    shared_packages=response['shared_packages'],
                    bandwidth=100,
                    last_seen=time.time(),
                    is_trusted=False,
                    reputation=0.5
                )
                
                self.peers[peer.id] = peer
                
                # Update shared packages
                for package in peer.shared_packages:
                    self.shared_packages[package].add(peer.id)
                
                client_socket.close()
                return True
            
            client_socket.close()
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to connect to peer {address}:{port}: {e}")
            return False
    
    def get_peer_stats(self) -> Dict:
        """Get P2P network statistics."""
        return {
            'total_peers': len(self.peers),
            'active_peers': len([p for p in self.peers.values() 
                               if time.time() - p.last_seen < self.peer_timeout]),
            'shared_packages': len(self.shared_packages),
            'total_shared_packages': sum(len(packages) for packages in self.shared_packages.values()),
            'peer_list': [
                {
                    'id': peer.id,
                    'address': f"{peer.address}:{peer.port}",
                    'capabilities': peer.capabilities,
                    'shared_packages': len(peer.shared_packages),
                    'reputation': peer.reputation,
                    'last_seen': peer.last_seen
                }
                for peer in self.peers.values()
            ]
        }

class DistributionManager:
    """Main distribution management system."""
    
    def __init__(self, mode: DistributionMode = DistributionMode.HYBRID):
        self.mode = mode
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.bandwidth_manager = BandwidthManager()
        self.mirror_manager = MirrorManager()
        self.p2p_manager = P2PDistributionManager()
        
        # Package cache
        self.package_cache: Dict[str, PackageInfo] = {}
        self.download_cache = Path("download_cache")
        self.download_cache.mkdir(exist_ok=True)
        
        # Download tracking
        self.active_downloads: Dict[str, Dict] = {}
        self.download_history: List[Dict] = []
    
    async def download_package(self, package_name: str, manager: str, 
                             version: str = None, use_p2p: bool = True) -> str:
        """Download a package using the best available method."""
        package_key = f"{manager}:{package_name}:{version or 'latest'}"
        
        # Check cache first
        cache_path = self.download_cache / f"{package_key}.pkg"
        if cache_path.exists():
            self.logger.info(f"Package {package_name} found in cache")
            return str(cache_path)
        
        # Get package info
        package_info = await self._get_package_info(package_name, manager, version)
        if not package_info:
            raise ValueError(f"Package {package_name} not found")
        
        # Choose download method
        if use_p2p and self.mode in [DistributionMode.P2P, DistributionMode.HYBRID]:
            # Try P2P first
            try:
                return await self._download_via_p2p(package_info)
            except Exception as e:
                self.logger.warning(f"P2P download failed: {e}")
        
        # Fall back to mirror download
        return await self._download_via_mirror(package_info)
    
    async def _get_package_info(self, package_name: str, manager: str, 
                               version: str = None) -> Optional[PackageInfo]:
        """Get package information."""
        # This would typically query package repositories
        # For now, return dummy info
        return PackageInfo(
            name=package_name,
            manager=manager,
            version=version or "latest",
            size=1024 * 1024,  # 1MB
            checksum="dummy_checksum",
            mirrors=[],
            chunks=[],
            chunk_size=1024 * 1024,
            total_chunks=1
        )
    
    async def _download_via_p2p(self, package_info: PackageInfo) -> str:
        """Download package via P2P network."""
        self.logger.info(f"Downloading {package_info.name} via P2P")
        
        # Find peers with this package
        peers_with_package = self.p2p_manager.shared_packages.get(
            f"{package_info.manager}:{package_info.name}", set()
        )
        
        if not peers_with_package:
            raise Exception("No peers have this package")
        
        # Choose best peer
        best_peer = None
        best_score = 0
        
        for peer_id in peers_with_package:
            if peer_id in self.p2p_manager.peers:
                peer = self.p2p_manager.peers[peer_id]
                score = peer.reputation * peer.bandwidth
                if score > best_score:
                    best_score = score
                    best_peer = peer
        
        if not best_peer:
            raise Exception("No suitable peer found")
        
        # Download from peer
        return await self._download_from_peer(best_peer, package_info)
    
    async def _download_from_peer(self, peer: PeerNode, package_info: PackageInfo) -> str:
        """Download package from a specific peer."""
        # This would implement the actual P2P download protocol
        # For now, return a dummy path
        cache_path = self.download_cache / f"{package_info.manager}_{package_info.name}.pkg"
        
        # Simulate download
        await asyncio.sleep(1)
        
        # Create dummy file
        with open(cache_path, 'wb') as f:
            f.write(b"dummy_package_data")
        
        return str(cache_path)
    
    async def _download_via_mirror(self, package_info: PackageInfo) -> str:
        """Download package via mirror."""
        self.logger.info(f"Downloading {package_info.name} via mirror")
        
        # Get best mirrors
        mirrors = self.mirror_manager.get_best_mirrors(package_info.manager, 3)
        
        if not mirrors:
            raise Exception("No suitable mirrors available")
        
        # Try mirrors in order
        for mirror in mirrors:
            try:
                return await self._download_from_mirror(mirror, package_info)
            except Exception as e:
                self.logger.warning(f"Download from mirror {mirror.name} failed: {e}")
                continue
        
        raise Exception("All mirrors failed")
    
    async def _download_from_mirror(self, mirror: Mirror, package_info: PackageInfo) -> str:
        """Download package from a specific mirror."""
        # Allocate bandwidth
        connection_id = f"mirror_{mirror.id}_{package_info.name}"
        allocated_bandwidth = self.bandwidth_manager.allocate_bandwidth(
            connection_id, mirror.bandwidth, 'adaptive'
        )
        
        try:
            # Calculate download time
            download_time = package_info.size / (allocated_bandwidth * 1024 * 1024 / 8)
            
            # Simulate download
            await asyncio.sleep(min(download_time, 5))  # Cap at 5 seconds for demo
            
            # Create cache file
            cache_path = self.download_cache / f"{package_info.manager}_{package_info.name}.pkg"
            
            with open(cache_path, 'wb') as f:
                f.write(b"dummy_package_data")
            
            # Update mirror status
            self.mirror_manager.update_mirror_status(
                mirror.id, MirrorStatus.ONLINE, download_time, True
            )
            
            return str(cache_path)
            
        finally:
            # Release bandwidth
            self.bandwidth_manager.release_bandwidth(connection_id)
    
    def get_distribution_stats(self) -> Dict:
        """Get distribution statistics."""
        return {
            'mode': self.mode.value,
            'bandwidth': self.bandwidth_manager.get_usage_stats(),
            'mirrors': {
                'total': len(self.mirror_manager.mirrors),
                'online': len([m for m in self.mirror_manager.mirrors.values() 
                             if m.status == MirrorStatus.ONLINE]),
                'offline': len([m for m in self.mirror_manager.mirrors.values() 
                              if m.status == MirrorStatus.OFFLINE])
            },
            'p2p': self.p2p_manager.get_peer_stats(),
            'cache': {
                'cached_packages': len(list(self.download_cache.glob("*.pkg"))),
                'cache_size': sum(f.stat().st_size for f in self.download_cache.glob("*.pkg"))
            }
        }
    
    def cleanup_cache(self, max_age_days: int = 7):
        """Clean up old cached packages."""
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        for cache_file in self.download_cache.glob("*.pkg"):
            if cache_file.stat().st_mtime < cutoff_time:
                cache_file.unlink()
                self.logger.info(f"Removed old cache file: {cache_file.name}")

# Global distribution manager instance
distribution_manager = DistributionManager() 