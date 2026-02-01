# backend/app/main.py
"""
ROS Code Intelligence Platform - Main API
Author: Haifa Jendoubi
Date: January 31, 2026
"""

import uuid
import zipfile
import shutil
import aiofiles
import logging
from pathlib import Path
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    UploadResponse,
    TreeResponse,
    AnalysisResponse,
    GraphResponse,
    HealthResponse,
    ErrorResponse
)
from .parsers import RosModel, parse_project
from .file_tree import build_file_tree
from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global cache for parsed models
analysis_cache: Dict[str, RosModel] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting ROS Code Intelligence Platform")
    settings.BASE_UPLOAD_DIR.mkdir(exist_ok=True)
    settings.TEMP_EXTRACT_DIR.mkdir(exist_ok=True)
    logger.info(f"📁 Upload directory: {settings.BASE_UPLOAD_DIR}")
    logger.info(f"📁 Extract directory: {settings.TEMP_EXTRACT_DIR}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down ROS Code Intelligence Platform")
    analysis_cache.clear()


# FastAPI Application
app = FastAPI(
    title="ROS Code Intelligence Platform API",
    description="""
    ## 🚀 Advanced Static Analysis Platform for ROS 1 Projects
    
    This API provides comprehensive analysis of ROS 1 packages including:
    - 📦 Project file tree visualization
    - 🤖 Node, topic, service, and parameter detection
    - 🔄 Communication flow analysis
    - ⚠️ Best practice warnings and code quality checks
    - 🎨 Interactive communication graph generation
    
    ### Features
    - Multi-language support (Python, C++, XML)
    - Intelligent deduplication
    - AST-based parsing for Python
    - Regex parsing for C++
    - Launch file interpretation
    
    ### Author
    Haifa Jendoubi - Robotics Software Engineer
    """,
    version="1.0.0",
    contact={
        "name": "Haifa Jendoubi",
        "email": "haifajendoubi65@gmail.com",
        "url": "https://github.com/HaifaJendoubi"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status="error",
            message=exc.detail,
            code=exc.status_code
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            status="error",
            message="Internal server error",
            code=500
        ).dict()
    )


# ============================================
# API ENDPOINTS
# ============================================

@app.get(
    "/",
    summary="API Root",
    description="Get API information and available endpoints"
)
async def root():
    """Root endpoint providing API overview"""
    return {
        "name": "ROS Code Intelligence Platform API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "health": "/api/health",
            "upload": "/api/upload-zip/",
            "tree": "/api/project-tree/{analysis_id}",
            "analyze": "/api/analyze/{analysis_id}",
            "graph": "/api/graph/{analysis_id}"
        }
    }


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API is running and healthy",
    tags=["System"]
)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        HealthResponse: API health status
    """
    return HealthResponse(
        status="healthy",
        message="ROS Code Intelligence Platform API is running",
        version="1.0.0",
        cached_analyses=len(analysis_cache)
    )


@app.post(
    "/api/upload-zip/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ROS Project",
    description="Upload a ZIP file containing a ROS 1 project for analysis",
    tags=["Upload"]
)
async def upload_and_extract_zip(
    file: UploadFile = File(..., description="ZIP archive of ROS project")
):
    """
    Upload and extract a ROS project ZIP file
    
    Args:
        file: ZIP archive containing ROS package
        
    Returns:
        UploadResponse: Upload status and analysis ID
        
    Raises:
        HTTPException: If file is not a ZIP or extraction fails
    """
    # Validate file type
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP files are allowed. Please upload a .zip archive."
        )
    
    # Validate file size (max 100MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds maximum allowed size ({settings.MAX_FILE_SIZE / 1024 / 1024} MB)"
        )
    
    # Generate unique analysis ID
    analysis_id = uuid.uuid4().hex[:12]
    zip_path = settings.BASE_UPLOAD_DIR / f"{analysis_id}_{file.filename}"
    
    logger.info(f"📤 Uploading file: {file.filename} (Analysis ID: {analysis_id})")
    
    # Save uploaded file
    try:
        async with aiofiles.open(zip_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )
    
    # Extract ZIP
    extract_folder = settings.TEMP_EXTRACT_DIR / analysis_id
    extract_folder.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_folder)
        logger.info(f"✅ Successfully extracted to: {extract_folder}")
    except zipfile.BadZipFile:
        shutil.rmtree(extract_folder, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ZIP file. The file appears to be corrupted."
        )
    except Exception as e:
        shutil.rmtree(extract_folder, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        logger.error(f"Extraction failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )
    
    # Clean up ZIP file
    zip_path.unlink(missing_ok=True)
    
    # Count extracted files
    file_count = sum(1 for _ in extract_folder.rglob("*") if _.is_file())
    
    logger.info(f"📊 Extracted {file_count} files")
    
    return UploadResponse(
        status="success",
        analysis_id=analysis_id,
        original_filename=file.filename,
        extracted_to=str(extract_folder.relative_to(settings.TEMP_EXTRACT_DIR)),
        file_count=file_count,
        message="Project uploaded and extracted successfully"
    )


@app.get(
    "/api/project-tree/{analysis_id}",
    response_model=TreeResponse,
    summary="Get Project Tree",
    description="Retrieve the file tree structure of an uploaded project",
    tags=["Project"]
)
async def get_project_tree(analysis_id: str):
    """
    Get the file tree structure of a project
    
    Args:
        analysis_id: Unique identifier for the analysis
        
    Returns:
        TreeResponse: Project file tree structure
        
    Raises:
        HTTPException: If project not found
    """
    project_dir = settings.TEMP_EXTRACT_DIR / analysis_id
    
    if not project_dir.is_dir():
        logger.warning(f"Project not found: {analysis_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{analysis_id}' not found. Please upload a project first."
        )
    
    logger.info(f"🌳 Building file tree for: {analysis_id}")
    
    # Find root directory (handle single-folder ZIPs)
    contents = list(project_dir.iterdir())
    root_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else project_dir
    
    try:
        tree = build_file_tree(root_dir)
        logger.info(f"✅ File tree built successfully")
        
        return TreeResponse(
            status="success",
            analysis_id=analysis_id,
            root_name=root_dir.name,
            tree=tree
        )
    except Exception as e:
        logger.error(f"Failed to build file tree: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build file tree: {str(e)}"
        )


@app.get(
    "/api/analyze/{analysis_id}",
    response_model=AnalysisResponse,
    summary="Analyze Project",
    description="Perform comprehensive ROS analysis on the uploaded project",
    tags=["Analysis"]
)
async def analyze_project(analysis_id: str):
    """
    Analyze ROS project and extract nodes, topics, services, parameters
    
    Args:
        analysis_id: Unique identifier for the analysis
        
    Returns:
        AnalysisResponse: Complete analysis results including metrics and warnings
        
    Raises:
        HTTPException: If project not found or analysis fails
    """
    project_dir = settings.TEMP_EXTRACT_DIR / analysis_id
    
    if not project_dir.is_dir():
        logger.warning(f"Project not found: {analysis_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{analysis_id}' not found"
        )
    
    logger.info(f"🔍 Analyzing project: {analysis_id}")
    
    # Check cache
    if analysis_id not in analysis_cache:
        try:
            analysis_cache[analysis_id] = parse_project(project_dir)
            logger.info(f"✅ Project parsed and cached")
        except Exception as e:
            logger.error(f"Failed to parse project: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse project: {str(e)}"
            )
    else:
        logger.info(f"📦 Using cached analysis")
    
    model = analysis_cache[analysis_id]
    
    # Prepare response data
    topics_list = list(model.topics.values())
    services_list = list(model.services.values())
    
    metrics = {
        "nodes_count": len(model.nodes),
        "topics_count": len(topics_list),
        "publishers_count": sum(len(set(t.publishers)) for t in topics_list),
        "subscribers_count": sum(len(set(t.subscribers)) for t in topics_list),
        "services_count": len(services_list),
        "parameters_count": len(model.parameters),
    }
    
    # Generate behavior summary
    behavior_lines = []
    
    if topics_list:
        for t in topics_list:
            p = ", ".join(set(t.publishers)) or "none"
            s = ", ".join(set(t.subscribers)) or "none"
            behavior_lines.append(f"• {t.name} ({t.message_type}): pub {p} → sub {s}")
    
    if services_list:
        for s in services_list:
            srv = ", ".join(s.servers) or "none"
            cli = ", ".join(s.clients) or "none"
            behavior_lines.append(f"• Service {s.name} ({s.type}): server {srv} ↔ client {cli}")
    
    behavior_summary = (
        "**Detected ROS Communication:**\n\n" + "\n".join(behavior_lines)
        if behavior_lines
        else "No ROS communication patterns detected in this project."
    )
    
    logger.info(f"📊 Analysis complete - Nodes: {metrics['nodes_count']}, Topics: {metrics['topics_count']}")
    
    return AnalysisResponse(
        status="analyzed",
        analysis_id=analysis_id,
        nodes=model.nodes,
        topics=topics_list,
        services=services_list,
        parameters=list(model.parameters),
        metrics=metrics,
        behavior_summary=behavior_summary,
        warnings=model.warnings
    )


@app.get(
    "/api/graph/{analysis_id}",
    response_model=GraphResponse,
    summary="Get Communication Graph",
    description="Generate interactive communication graph showing nodes, topics, and connections",
    tags=["Graph"]
)
async def get_communication_graph(analysis_id: str):
    """
    Get communication graph for visualization
    
    Args:
        analysis_id: Unique identifier for the analysis
        
    Returns:
        GraphResponse: Graph nodes and edges for visualization
        
    Raises:
        HTTPException: If project not found
    """
    project_dir = settings.TEMP_EXTRACT_DIR / analysis_id
    
    if not project_dir.is_dir():
        logger.warning(f"Project not found: {analysis_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{analysis_id}' not found"
        )
    
    logger.info(f"🎨 Generating communication graph for: {analysis_id}")
    
    # Parse if not cached
    if analysis_id not in analysis_cache:
        try:
            analysis_cache[analysis_id] = parse_project(project_dir)
        except Exception as e:
            logger.error(f"Failed to parse project: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse project: {str(e)}"
            )
    
    model = analysis_cache[analysis_id]
    
    # Build graph
    from .models import GraphNode, GraphEdge
    
    nodes = [
        GraphNode(id=n.name, label=n.name, type="node")
        for n in model.nodes
    ]
    edges = []
    
    # Add topics and connections
    for idx, topic in enumerate(model.topics.values()):
        tid = f"topic_{idx}"
        nodes.append(GraphNode(id=tid, label=topic.name, type="topic"))
        
        for p in set(topic.publishers):
            edges.append(GraphEdge(
                id=f"pub_{p}_{tid}",
                source=p,
                target=tid,
                label=topic.message_type
            ))
        
        for s in set(topic.subscribers):
            edges.append(GraphEdge(
                id=f"sub_{tid}_{s}",
                source=tid,
                target=s,
                label=""
            ))
    
    # Add services and connections
    for idx, srv in enumerate(model.services.values()):
        sid = f"service_{idx}"
        nodes.append(GraphNode(id=sid, label=srv.name, type="service"))
        
        for server in srv.servers:
            edges.append(GraphEdge(
                id=f"srv_server_{server}_{sid}",
                source=server,
                target=sid,
                label="provides"
            ))
        
        for client in srv.clients:
            edges.append(GraphEdge(
                id=f"srv_client_{client}_{sid}",
                source=client,
                target=sid,
                label="calls"
            ))
    
    logger.info(f"✅ Graph generated - Nodes: {len(nodes)}, Edges: {len(edges)}")
    
    return GraphResponse(nodes=nodes, edges=edges)


# Development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
