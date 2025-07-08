"""Docker Integration Plugin for ZorOS

Provides Docker containerization and service management capabilities.
"""

from typing import Dict, Any, List, Optional
import logging
import subprocess
import json
import os

from source.plugins.base import ZorosPlugin

logger = logging.getLogger(__name__)


class DockerPlugin(ZorosPlugin):
    """Docker integration plugin for ZorOS."""
    
    @property
    def name(self) -> str:
        return "Docker Integration"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Docker containerization and service management for ZorOS components"
    
    @property
    def dependencies(self) -> List[str]:
        return [
            "docker",  # Python Docker SDK
            "docker-compose",
            "pyyaml"
        ]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return [
            "kubernetes",  # For k8s orchestration
            "docker-buildx"  # For multi-platform builds
        ]
    
    def initialize(self, plugin_manager: Any) -> None:
        """Initialize the Docker plugin."""
        logger.info(f"Initializing {self.name}")
        
        # Check Docker availability
        if self._check_docker_available():
            logger.info("Docker is available and running")
            
            # Create docker-compose configuration for ZorOS services
            self._create_docker_compose_config()
            
            # Register Docker service management
            plugin_manager.register_service_manager("docker", self)
            
        else:
            logger.warning("Docker is not available - plugin running in limited mode")
        
        logger.info("Docker plugin initialized successfully")
    
    def _check_docker_available(self) -> bool:
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                # Also check if Docker daemon is running
                result = subprocess.run(
                    ["docker", "info"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                return result.returncode == 0
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _create_docker_compose_config(self) -> None:
        """Create docker-compose.yml for ZorOS services."""
        docker_compose_config = {
            "version": "3.8",
            "services": {
                "zoros-backend": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.backend"
                    },
                    "ports": ["8000:8000"],
                    "environment": [
                        "PYTHONPATH=/app",
                        "ZOROS_ENV=docker"
                    ],
                    "volumes": [
                        "./source:/app/source:ro",
                        "./backend:/app/backend:ro",
                        "zoros-data:/app/data"
                    ],
                    "depends_on": ["zoros-db"]
                },
                "zoros-frontend": {
                    "build": {
                        "context": "./zoros-frontend",
                        "dockerfile": "Dockerfile"
                    },
                    "ports": ["3000:3000"],
                    "environment": [
                        "REACT_APP_API_BASE_URL=http://localhost:8000"
                    ],
                    "depends_on": ["zoros-backend"]
                },
                "zoros-db": {
                    "image": "postgres:15-alpine",
                    "environment": [
                        "POSTGRES_DB=zoros",
                        "POSTGRES_USER=zoros",
                        "POSTGRES_PASSWORD=zoros_dev"
                    ],
                    "volumes": [
                        "postgres-data:/var/lib/postgresql/data"
                    ],
                    "ports": ["5432:5432"]
                },
                "whisper-service": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.whisper"
                    },
                    "ports": ["8001:8001"],
                    "environment": [
                        "MODEL_SIZE=base",
                        "DEVICE=cpu"
                    ],
                    "volumes": [
                        "whisper-models:/app/models"
                    ]
                }
            },
            "volumes": {
                "zoros-data": {},
                "postgres-data": {},
                "whisper-models": {}
            },
            "networks": {
                "zoros-network": {
                    "driver": "bridge"
                }
            }
        }
        
        # Write docker-compose.yml
        with open("docker-compose.yml", "w") as f:
            import yaml
            yaml.dump(docker_compose_config, f, default_flow_style=False)
        
        logger.info("Created docker-compose.yml configuration")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the Docker plugin."""
        status = {
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "details": {
                "docker_available": False,
                "docker_compose_available": False,
                "running_containers": 0,
                "services_status": {}
            }
        }
        
        try:
            # Check Docker availability
            status["details"]["docker_available"] = self._check_docker_available()
            
            # Check docker-compose availability
            result = subprocess.run(
                ["docker-compose", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            status["details"]["docker_compose_available"] = result.returncode == 0
            
            # Get running containers
            if status["details"]["docker_available"]:
                containers = self._get_running_containers()
                status["details"]["running_containers"] = len(containers)
                status["details"]["services_status"] = self._get_services_status()
            
        except Exception as e:
            status["status"] = "degraded"
            status["details"]["error"] = str(e)
        
        return status
    
    def _get_running_containers(self) -> List[Dict[str, Any]]:
        """Get list of running Docker containers."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "json"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        containers.append(json.loads(line))
                return containers
            return []
        except Exception:
            return []
    
    def _get_services_status(self) -> Dict[str, str]:
        """Get status of ZorOS services."""
        try:
            result = subprocess.run(
                ["docker-compose", "ps", "--format", "json"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                services = {}
                for line in result.stdout.strip().split('\n'):
                    if line:
                        service_info = json.loads(line)
                        services[service_info.get("Service", "unknown")] = service_info.get("State", "unknown")
                return services
            return {}
        except Exception:
            return {}
    
    def start_services(self, services: Optional[List[str]] = None) -> Dict[str, Any]:
        """Start ZorOS services using Docker Compose."""
        try:
            cmd = ["docker-compose", "up", "-d"]
            if services:
                cmd.extend(services)
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": "Services started successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to start services",
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error starting services: {str(e)}"
            }
    
    def stop_services(self, services: Optional[List[str]] = None) -> Dict[str, Any]:
        """Stop ZorOS services using Docker Compose."""
        try:
            cmd = ["docker-compose", "down"]
            if services:
                cmd = ["docker-compose", "stop"] + services
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": "Services stopped successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to stop services",
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error stopping services: {str(e)}"
            }
    
    def build_images(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build Docker images for ZorOS services."""
        try:
            cmd = ["docker-compose", "build"]
            if force_rebuild:
                cmd.append("--no-cache")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minutes for builds
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": "Images built successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to build images",
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error building images: {str(e)}"
            }
    
    def get_logs(self, service: Optional[str] = None, lines: int = 100) -> Dict[str, Any]:
        """Get logs from Docker services."""
        try:
            cmd = ["docker-compose", "logs", "--tail", str(lines)]
            if service:
                cmd.append(service)
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            return {
                "status": "success",
                "logs": result.stdout,
                "service": service or "all"
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting logs: {str(e)}"
            }