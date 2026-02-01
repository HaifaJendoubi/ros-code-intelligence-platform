# backend/app/models.py
"""
Pydantic models for request/response validation
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ============================================
# RESPONSE MODELS
# ============================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Status message")
    version: str = Field(..., description="API version")
    cached_analyses: int = Field(..., description="Number of cached analyses")


class ErrorResponse(BaseModel):
    """Error response"""
    status: str = Field(default="error", description="Status")
    message: str = Field(..., description="Error message")
    code: int = Field(..., description="HTTP status code")


class UploadResponse(BaseModel):
    """Upload operation response"""
    status: str = Field(..., description="Operation status")
    analysis_id: str = Field(..., description="Unique analysis identifier")
    original_filename: str = Field(..., description="Original ZIP filename")
    extracted_to: str = Field(..., description="Extraction path")
    file_count: int = Field(..., description="Number of extracted files")
    message: str = Field(..., description="Success message")


# ============================================
# FILE TREE MODELS
# ============================================

class FileNode(BaseModel):
    """File tree node"""
    name: str = Field(..., description="File or folder name")
    path: str = Field(..., description="Relative path")
    type: str = Field(..., description="Type: 'file' or 'folder'")
    size: Optional[int] = Field(None, description="File size in bytes")
    children: Optional[List["FileNode"]] = Field(None, description="Child nodes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "src",
                "path": "my_package/src",
                "type": "folder",
                "children": [
                    {
                        "name": "node.py",
                        "path": "my_package/src/node.py",
                        "type": "file",
                        "size": 2048
                    }
                ]
            }
        }


class TreeResponse(BaseModel):
    """Project tree response"""
    status: str = Field(..., description="Operation status")
    analysis_id: str = Field(..., description="Analysis identifier")
    root_name: str = Field(..., description="Root directory name")
    tree: FileNode = Field(..., description="File tree structure")


# ============================================
# ROS ANALYSIS MODELS
# ============================================

class NodeInfo(BaseModel):
    """ROS node information"""
    name: str = Field(..., description="Node name")
    file: str = Field(..., description="Source file path")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "camera_publisher",
                "file": "src/camera_publisher.py"
            }
        }


class TopicInfo(BaseModel):
    """ROS topic information"""
    name: str = Field(..., description="Topic name")
    message_type: str = Field(..., description="Message type")
    publishers: List[str] = Field(default_factory=list, description="Publishing nodes")
    subscribers: List[str] = Field(default_factory=list, description="Subscribing nodes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "/camera/image",
                "message_type": "sensor_msgs/Image",
                "publishers": ["camera_publisher"],
                "subscribers": ["image_processor"]
            }
        }


class ServiceInfo(BaseModel):
    """ROS service information"""
    name: str = Field(..., description="Service name")
    type: str = Field(..., description="Service type")
    servers: List[str] = Field(default_factory=list, description="Service servers")
    clients: List[str] = Field(default_factory=list, description="Service clients")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "/camera/set_parameters",
                "type": "std_srvs/SetParameters",
                "servers": ["camera_node"],
                "clients": ["config_manager"]
            }
        }


class AnalysisResponse(BaseModel):
    """Complete analysis response"""
    status: str = Field(..., description="Analysis status")
    analysis_id: str = Field(..., description="Analysis identifier")
    nodes: List[NodeInfo] = Field(..., description="Detected ROS nodes")
    topics: List[TopicInfo] = Field(..., description="Detected topics")
    services: List[ServiceInfo] = Field(..., description="Detected services")
    parameters: List[str] = Field(..., description="Detected parameters")
    metrics: Dict[str, int] = Field(..., description="Analysis metrics")
    behavior_summary: str = Field(..., description="Communication behavior summary")
    warnings: List[str] = Field(..., description="Code quality warnings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "analyzed",
                "analysis_id": "abc123def456",
                "nodes": [
                    {"name": "talker", "file": "src/talker.py"},
                    {"name": "listener", "file": "src/listener.py"}
                ],
                "topics": [
                    {
                        "name": "/chatter",
                        "message_type": "std_msgs/String",
                        "publishers": ["talker"],
                        "subscribers": ["listener"]
                    }
                ],
                "services": [],
                "parameters": ["publish_rate"],
                "metrics": {
                    "nodes_count": 2,
                    "topics_count": 1,
                    "publishers_count": 1,
                    "subscribers_count": 1,
                    "services_count": 0,
                    "parameters_count": 1
                },
                "behavior_summary": "**Detected ROS Communication:**\n\n• /chatter (std_msgs/String): pub talker → sub listener",
                "warnings": []
            }
        }


# ============================================
# GRAPH MODELS
# ============================================

class GraphNode(BaseModel):
    """Graph node for visualization"""
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display label")
    type: str = Field(..., description="Node type: 'node', 'topic', or 'service'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "camera_publisher",
                "label": "camera_publisher",
                "type": "node"
            }
        }


class GraphEdge(BaseModel):
    """Graph edge for visualization"""
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: str = Field(..., description="Edge label")
    animated: bool = Field(default=True, description="Animation flag")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "pub_camera_publisher_topic_0",
                "source": "camera_publisher",
                "target": "topic_0",
                "label": "sensor_msgs/Image",
                "animated": True
            }
        }


class GraphResponse(BaseModel):
    """Communication graph response"""
    nodes: List[GraphNode] = Field(..., description="Graph nodes")
    edges: List[GraphEdge] = Field(..., description="Graph edges")
    
    class Config:
        json_schema_extra = {
            "example": {
                "nodes": [
                    {"id": "talker", "label": "talker", "type": "node"},
                    {"id": "listener", "label": "listener", "type": "node"},
                    {"id": "topic_0", "label": "/chatter", "type": "topic"}
                ],
                "edges": [
                    {
                        "id": "pub_talker_topic_0",
                        "source": "talker",
                        "target": "topic_0",
                        "label": "std_msgs/String",
                        "animated": True
                    },
                    {
                        "id": "sub_topic_0_listener",
                        "source": "topic_0",
                        "target": "listener",
                        "label": "",
                        "animated": True
                    }
                ]
            }
        }


# Update forward references
FileNode.model_rebuild()