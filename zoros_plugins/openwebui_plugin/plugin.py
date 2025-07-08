"""OpenWebUI Integration Plugin for ZorOS

Provides OpenWebUI integration for web-based LLM interfaces
and chat management without requiring Docker.
"""

from typing import Dict, Any, List, Optional
import logging
import subprocess
import json
import requests
import os
import threading
import time

from source.plugins.base import ZorosPlugin

logger = logging.getLogger(__name__)


class OpenWebUIPlugin(ZorosPlugin):
    """OpenWebUI integration plugin for ZorOS."""
    
    def __init__(self):
        self._webui_process = None
        self._webui_port = 8080
        self._webui_host = "127.0.0.1"
        self._api_base_url = None
    
    @property
    def name(self) -> str:
        return "OpenWebUI Integration"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "OpenWebUI integration for web-based LLM interfaces and chat management"
    
    @property
    def dependencies(self) -> List[str]:
        return [
            "requests",
            "aiohttp",
            "fastapi"
        ]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return [
            "open-webui",  # If available as pip package
            "ollama",  # For local model serving
            "litellm"  # For multi-provider LLM support
        ]
    
    def initialize(self, plugin_manager: Any) -> None:
        """Initialize the OpenWebUI plugin."""
        logger.info(f"Initializing {self.name}")
        
        # Set API base URL
        self._api_base_url = f"http://{self._webui_host}:{self._webui_port}/api"
        
        # Check if OpenWebUI is available
        if self._check_openwebui_available():
            logger.info("OpenWebUI is available")
            
            # Register OpenWebUI services
            plugin_manager.register_chat_interface("openwebui", self)
            plugin_manager.register_model_manager("openwebui", self)
            
        else:
            logger.info("OpenWebUI not found - will attempt to install/setup when needed")
        
        logger.info("OpenWebUI plugin initialized successfully")
    
    def _check_openwebui_available(self) -> bool:
        """Check if OpenWebUI is available."""
        try:
            # Try to import open-webui if installed as package
            import importlib
            importlib.import_module("open_webui")
            return True
        except ImportError:
            pass
        
        # Check if running as service
        try:
            response = requests.get(f"{self._api_base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            pass
        
        # Check if executable exists
        try:
            result = subprocess.run(
                ["which", "open-webui"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        
        return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the OpenWebUI plugin."""
        status = {
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "details": {
                "webui_available": False,
                "webui_running": False,
                "api_accessible": False,
                "active_models": [],
                "active_chats": 0
            }
        }
        
        try:
            # Check if OpenWebUI is available
            status["details"]["webui_available"] = self._check_openwebui_available()
            
            # Check if service is running
            if self._webui_process and self._webui_process.poll() is None:
                status["details"]["webui_running"] = True
            
            # Check API accessibility
            try:
                response = requests.get(f"{self._api_base_url}/health", timeout=5)
                status["details"]["api_accessible"] = response.status_code == 200
                
                if status["details"]["api_accessible"]:
                    # Get additional status info
                    models = self._get_available_models()
                    status["details"]["active_models"] = models
                    
                    chats = self._get_active_chats()
                    status["details"]["active_chats"] = len(chats)
                
            except requests.RequestException:
                status["details"]["api_accessible"] = False
            
        except Exception as e:
            status["status"] = "degraded"
            status["details"]["error"] = str(e)
        
        return status
    
    def start_webui(self, port: Optional[int] = None, host: str = "127.0.0.1") -> Dict[str, Any]:
        """Start OpenWebUI service."""
        if port:
            self._webui_port = port
        self._webui_host = host
        self._api_base_url = f"http://{self._webui_host}:{self._webui_port}/api"
        
        try:
            # Check if already running
            if self._webui_process and self._webui_process.poll() is None:
                return {
                    "status": "already_running",
                    "message": f"OpenWebUI already running on {self._webui_host}:{self._webui_port}"
                }
            
            # Try different startup methods
            startup_methods = [
                self._start_with_pip_package,
                self._start_with_executable,
                self._start_with_docker_fallback
            ]
            
            for method in startup_methods:
                result = method()
                if result["status"] == "success":
                    # Wait for service to be ready
                    if self._wait_for_service_ready():
                        return result
                    else:
                        return {
                            "status": "error",
                            "message": "Service started but not responding"
                        }
            
            return {
                "status": "error",
                "message": "Failed to start OpenWebUI with any available method"
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error starting OpenWebUI: {str(e)}"
            }
    
    def _start_with_pip_package(self) -> Dict[str, Any]:
        """Try to start OpenWebUI using pip package."""
        try:
            # Check if open_webui module exists first
            try:
                import importlib
                importlib.import_module("open_webui")
            except ImportError:
                return {"status": "failed", "error": "open_webui module not available"}
            
            # Try to start as Python module
            cmd = [
                "python", "-m", "open_webui",
                "--host", self._webui_host,
                "--port", str(self._webui_port)
            ]
            
            self._webui_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return {
                "status": "success",
                "method": "pip_package",
                "message": f"Started OpenWebUI on {self._webui_host}:{self._webui_port}"
            }
        
        except Exception as e:
            logger.debug(f"Failed to start with pip package: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _start_with_executable(self) -> Dict[str, Any]:
        """Try to start OpenWebUI using executable."""
        try:
            # Check if executable exists first
            result = subprocess.run(
                ["which", "open-webui"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode != 0:
                return {"status": "failed", "error": "open-webui executable not found"}
            
            cmd = [
                "open-webui",
                "serve",
                "--host", self._webui_host,
                "--port", str(self._webui_port)
            ]
            
            self._webui_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return {
                "status": "success",
                "method": "executable",
                "message": f"Started OpenWebUI on {self._webui_host}:{self._webui_port}"
            }
        
        except Exception as e:
            logger.debug(f"Failed to start with executable: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _start_with_docker_fallback(self) -> Dict[str, Any]:
        """Try to start OpenWebUI using Docker as fallback."""
        try:
            cmd = [
                "docker", "run", "-d",
                "--name", "zoros-openwebui",
                "-p", f"{self._webui_port}:8080",
                "-v", "open-webui:/app/backend/data",
                "--restart", "unless-stopped",
                "ghcr.io/open-webui/open-webui:main"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "method": "docker",
                    "message": f"Started OpenWebUI container on port {self._webui_port}",
                    "container_id": result.stdout.strip()
                }
            else:
                return {
                    "status": "failed",
                    "error": result.stderr
                }
        
        except Exception as e:
            logger.debug(f"Failed to start with Docker: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _wait_for_service_ready(self, timeout: int = 30) -> bool:
        """Wait for OpenWebUI service to be ready."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self._api_base_url}/health", timeout=2)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            
            time.sleep(1)
        
        return False
    
    def stop_webui(self) -> Dict[str, Any]:
        """Stop OpenWebUI service."""
        try:
            if self._webui_process and self._webui_process.poll() is None:
                self._webui_process.terminate()
                self._webui_process.wait(timeout=10)
                
                return {
                    "status": "success",
                    "message": "OpenWebUI stopped successfully"
                }
            else:
                # Try to stop Docker container if running
                try:
                    subprocess.run(
                        ["docker", "stop", "zoros-openwebui"],
                        capture_output=True,
                        timeout=10
                    )
                    subprocess.run(
                        ["docker", "rm", "zoros-openwebui"],
                        capture_output=True,
                        timeout=10
                    )
                except subprocess.TimeoutExpired:
                    pass
                
                return {
                    "status": "success",
                    "message": "OpenWebUI was not running"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error stopping OpenWebUI: {str(e)}"
            }
    
    def _get_available_models(self) -> List[str]:
        """Get list of available models."""
        try:
            response = requests.get(f"{self._api_base_url}/models", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                return [model.get("id", "") for model in models_data.get("data", [])]
            return []
        except requests.RequestException:
            return []
    
    def _get_active_chats(self) -> List[Dict[str, Any]]:
        """Get list of active chats."""
        try:
            response = requests.get(f"{self._api_base_url}/chats", timeout=5)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.RequestException:
            return []
    
    def create_chat(self, title: str, model: str = "gpt-3.5-turbo") -> Dict[str, Any]:
        """Create a new chat session."""
        try:
            payload = {
                "title": title,
                "model": model,
                "messages": []
            }
            
            response = requests.post(
                f"{self._api_base_url}/chats",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "chat_id": response.json().get("id"),
                    "title": title,
                    "model": model
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create chat: {response.text}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error creating chat: {str(e)}"
            }
    
    def send_message(self, chat_id: str, message: str, model: str = "gpt-3.5-turbo") -> Dict[str, Any]:
        """Send a message in a chat session."""
        try:
            payload = {
                "message": message,
                "model": model,
                "stream": False
            }
            
            response = requests.post(
                f"{self._api_base_url}/chats/{chat_id}/messages",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return {
                    "status": "success",
                    "response": response_data.get("message", ""),
                    "model": model,
                    "chat_id": chat_id
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to send message: {response.text}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error sending message: {str(e)}"
            }
    
    def get_chat_history(self, chat_id: str) -> Dict[str, Any]:
        """Get chat history for a session."""
        try:
            response = requests.get(f"{self._api_base_url}/chats/{chat_id}", timeout=10)
            
            if response.status_code == 200:
                chat_data = response.json()
                return {
                    "status": "success",
                    "chat_id": chat_id,
                    "title": chat_data.get("title", ""),
                    "messages": chat_data.get("messages", []),
                    "model": chat_data.get("model", "")
                }
            else:
                return {
                    "status": "error",
                    "message": f"Chat not found: {response.text}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting chat history: {str(e)}"
            }
    
    def integrate_with_zoros_fibers(self, fiber_content: str, model: str = "gpt-3.5-turbo") -> Dict[str, Any]:
        """Integrate ZorOS Fibers with OpenWebUI for processing."""
        try:
            # Create a new chat for fiber processing
            chat_result = self.create_chat(
                title=f"Fiber Processing - {fiber_content[:50]}...",
                model=model
            )
            
            if chat_result["status"] != "success":
                return chat_result
            
            chat_id = chat_result["chat_id"]
            
            # Send fiber content for processing
            processing_prompt = f"""
            Please analyze and process this ZorOS Fiber content:
            
            {fiber_content}
            
            Provide:
            1. Summary of the content
            2. Key themes or topics
            3. Suggested follow-up actions
            4. Potential thread connections
            """
            
            message_result = self.send_message(chat_id, processing_prompt, model)
            
            if message_result["status"] == "success":
                return {
                    "status": "success",
                    "chat_id": chat_id,
                    "fiber_analysis": message_result["response"],
                    "model": model,
                    "integration_type": "fiber_processing"
                }
            else:
                return message_result
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error integrating fiber with OpenWebUI: {str(e)}"
            }