# backend/app/main.py

import uuid
import zipfile
import shutil
import aiofiles
import ast
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Cache parsed models
analysis_cache: Dict[str, 'RosModel'] = {}

# Pydantic Models
class UploadResponse(BaseModel):
    status: str
    analysis_id: str
    original_filename: str
    extracted_to: str
    file_count: int
    message: str


class FileNode(BaseModel):
    name: str
    path: str
    type: str
    size: Optional[int] = None
    children: Optional[List["FileNode"]] = None


class TreeResponse(BaseModel):
    status: str
    analysis_id: str
    root_name: str
    tree: FileNode


class TopicInfo(BaseModel):
    name: str
    message_type: str
    publishers: List[str]
    subscribers: List[str]


class NodeInfo(BaseModel):
    name: str
    file: str


class ServiceInfo(BaseModel):
    name: str
    type: str
    servers: List[str]
    clients: List[str]


class AnalysisResponse(BaseModel):
    status: str
    analysis_id: str
    nodes: List[NodeInfo]
    topics: List[TopicInfo]
    services: List[ServiceInfo]
    parameters: List[str]
    metrics: Dict[str, int]
    behavior_summary: str
    warnings: List[str]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    animated: bool = True


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# FastAPI + CORS
app = FastAPI(
    title="ROS Code Intelligence Platform",
    description="Static analysis platform for ROS 1 projects",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_UPLOAD_DIR = Path("uploads")
TEMP_EXTRACT_DIR = Path("extracted_projects")

BASE_UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_EXTRACT_DIR.mkdir(exist_ok=True)


# File Tree Builder
def build_file_tree(path: Path) -> FileNode:
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")

    is_dir = path.is_dir()
    node = FileNode(
        name=path.name or "root",
        path=str(path.relative_to(TEMP_EXTRACT_DIR)),
        type="folder" if is_dir else "file",
        size=path.stat().st_size if not is_dir else None,
        children=[] if is_dir else None
    )

    if is_dir:
        for item in sorted(path.iterdir()):
            child = build_file_tree(item)
            if child.type == "folder" or child.name.lower().endswith((
                ".py", ".cpp", ".c", ".h", ".hpp", ".launch", ".xml", ".yaml", ".yml"
            )):
                node.children.append(child)

    return node


# ROS Model
class RosModel:
    def __init__(self):
        self.nodes: List[NodeInfo] = []
        self.node_names: Set[str] = set()
        self.topics: Dict[str, TopicInfo] = {}
        self.services: Dict[str, ServiceInfo] = {}
        self.parameters: Set[str] = set()
        self.warnings: List[str] = []

    def add_node(self, name: str, file_path: Path):
        """Deduplication: keep only ONE node per unique name (first source file wins)"""
        clean_file = str(file_path.relative_to(TEMP_EXTRACT_DIR)) if TEMP_EXTRACT_DIR in file_path.parents else file_path.name
        is_launch = file_path.suffix.lower() in ('.launch', '.xml')

        if name in self.node_names:
            existing = next((n for n in self.nodes if n.name == name), None)
            if existing:
                existing_is_launch = existing.file.lower().endswith(('.launch', '.xml'))

                # Case 1: Launch duplicate → ignore completely
                if is_launch:
                    return

                # Case 2: Source duplicate → warn, but keep only first occurrence
                if not is_launch:
                    self.warnings.append(
                        f"Duplicate node name '{name}' found in multiple source files: "
                        f"using {existing.file} (ignoring {clean_file})"
                    )
                    return  # Do NOT add duplicate

        # New unique node
        self.node_names.add(name)
        self.nodes.append(NodeInfo(name=name, file=clean_file))

    def add_pub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(name=topic, message_type=msg_type or "unknown", publishers=[], subscribers=[])
        if node not in self.topics[topic].publishers:
            self.topics[topic].publishers.append(node)

    def add_sub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(name=topic, message_type=msg_type or "unknown", publishers=[], subscribers=[])
        if node not in self.topics[topic].subscribers:
            self.topics[topic].subscribers.append(node)

    def add_service(self, service: str, srv_type: str, node: str, is_server: bool):
        if service not in self.services:
            self.services[service] = ServiceInfo(name=service, type=srv_type or "unknown", servers=[], clients=[])
        target = self.services[service].servers if is_server else self.services[service].clients
        if node not in target:
            target.append(node)

    def add_param(self, param: str):
        self.parameters.add(param)


# File Filtering
def is_relevant_source_file(path: Path) -> bool:
    path_str = str(path).lower()
    if any(x in path_str for x in ["/build/", "/devel/", "/install/", "/log/", "__pycache__", ".pyc", ".pyo"]):
        return False
    try:
        content = path.read_text(errors="ignore")
        if "generated from catkin/cmake/template/script.py.in" in content:
            return False
    except:
        pass
    return path.name.lower().endswith((".py", ".cpp", ".c", ".h", ".hpp", ".launch", ".xml", ".yaml", ".yml"))


# Python Parser
class ROSASTVisitor(ast.NodeVisitor):
    def __init__(self, model: RosModel, filepath: Path):
        self.model = model
        self.filepath = filepath
        self.current_node: Optional[str] = None
        self.pubs = []
        self.subs = []
        self.services = []
        self.params = []
        self.has_rate = False
        self.has_try = False

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "rospy":
                attr = node.func.attr

                if attr == "init_node" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    name = node.args[0].value
                    self.current_node = name
                    self.model.add_node(name, self.filepath)

                elif attr == "Publisher" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                    topic = node.args[0].value
                    msg_type = self._get_type(node.args[1])
                    self.pubs.append((topic, msg_type))

                elif attr == "Subscriber" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                    topic = node.args[0].value
                    msg_type = self._get_type(node.args[1])
                    self.subs.append((topic, msg_type))

                elif attr == "Service" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                    srv = node.args[0].value
                    typ = self._get_type(node.args[1])
                    self.services.append((srv, typ, True))

                elif attr == "ServiceProxy" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                    srv = node.args[0].value
                    typ = self._get_type(node.args[1])
                    self.services.append((srv, typ, False))

                elif attr in ("get_param", "set_param") and node.args and isinstance(node.args[0], ast.Constant):
                    self.params.append(node.args[0].value)

                elif attr == "Rate":
                    self.has_rate = True

        if isinstance(node, ast.Try):
            self.has_try = True

        self.generic_visit(node)

    def _get_type(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = node.value.id if isinstance(node.value, ast.Name) else "?"
            return f"{base}.{node.attr}"
        return "unknown"

    def finalize(self):
        if not self.current_node:
            return
        for t, m in self.pubs:
            self.model.add_pub(t, m, self.current_node)
        for t, m in self.subs:
            self.model.add_sub(t, m, self.current_node)
        for s, t, server in self.services:
            self.model.add_service(s, t, self.current_node, server)
        for p in self.params:
            self.model.add_param(p)

        if not self.has_rate:
            self.model.warnings.append(f"[{self.current_node}] Missing rospy.Rate → possible high CPU usage")
        if not self.has_try:
            self.model.warnings.append(f"[{self.current_node}] No try/except blocks → fragile error handling")


def parse_python_ros_file(filepath: Path, model: RosModel):
    if not is_relevant_source_file(filepath):
        return
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
        visitor = ROSASTVisitor(model, filepath)
        visitor.visit(tree)
        visitor.finalize()
    except Exception as e:
        model.warnings.append(f"Python parse error in {filepath.name}: {str(e)}")


# Launch & C++ Parsers
def parse_launch_file(filepath: Path, model: RosModel):
    if not filepath.name.lower().endswith(('.launch', '.xml')):
        return
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        for node_elem in root.findall('.//node'):
            name = node_elem.get('name')
            if name:
                model.add_node(name, filepath)
    except Exception as e:
        model.warnings.append(f"Launch parse error {filepath.name}: {str(e)}")


def parse_cpp_ros_file(filepath: Path, model: RosModel):
    if not filepath.suffix.lower() in ('.cpp', '.c', '.h', '.hpp'):
        return
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'ros::init\s*\([^,]+,\s*["\']([^"\']+)["\']', content):
            name = match.group(1)
            model.add_node(name, filepath)
    except Exception:
        pass


# Core Parsing – STRICT SOURCE-FIRST
def parse_project(project_dir: Path) -> RosModel:
    model = RosModel()

    # Phase 1: Sources first
    source_ext = {'.py', '.cpp', '.c', '.h', '.hpp'}
    source_files = []
    for ext in source_ext:
        source_files.extend(project_dir.rglob(f'*{ext}'))
    source_files.sort(key=str)

    for file in source_files:
        if file.suffix.lower() == '.py':
            parse_python_ros_file(file, model)
        else:
            parse_cpp_ros_file(file, model)

    # Phase 2: Launch last
    launch_files = list(project_dir.rglob('*.launch')) + list(project_dir.rglob('*.xml'))
    launch_files.sort(key=str)

    for file in launch_files:
        parse_launch_file(file, model)

    return model


# API Endpoints
@app.post("/api/upload-zip/", response_model=UploadResponse)
async def upload_and_extract_zip(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Only ZIP files allowed")

    analysis_id = uuid.uuid4().hex[:12]
    zip_path = BASE_UPLOAD_DIR / f"{analysis_id}_{file.filename}"

    async with aiofiles.open(zip_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    extract_folder = TEMP_EXTRACT_DIR / analysis_id
    extract_folder.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_folder)
    except Exception as e:
        shutil.rmtree(extract_folder, ignore_errors=True)
        raise HTTPException(400, f"Extraction failed: {str(e)}")

    zip_path.unlink(missing_ok=True)
    file_count = sum(1 for _ in extract_folder.rglob("*") if _.is_file())

    return UploadResponse(
        status="success",
        analysis_id=analysis_id,
        original_filename=file.filename,
        extracted_to=str(extract_folder),
        file_count=file_count,
        message="ZIP uploaded and extracted"
    )


@app.get("/api/project-tree/{analysis_id}", response_model=TreeResponse)
async def get_project_tree(analysis_id: str):
    project_dir = TEMP_EXTRACT_DIR / analysis_id
    if not project_dir.is_dir():
        raise HTTPException(404, "Project not found")

    contents = list(project_dir.iterdir())
    root_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else project_dir

    return TreeResponse(
        status="ok",
        analysis_id=analysis_id,
        root_name=root_dir.name,
        tree=build_file_tree(root_dir)
    )


@app.get("/api/analyze/{analysis_id}", response_model=AnalysisResponse)
async def analyze_project(analysis_id: str):
    project_dir = TEMP_EXTRACT_DIR / analysis_id
    if not project_dir.is_dir():
        raise HTTPException(404, "Project not found")

    if analysis_id not in analysis_cache:
        analysis_cache[analysis_id] = parse_project(project_dir)

    model = analysis_cache[analysis_id]

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

    behavior_lines = []
    for t in topics_list:
        p = ", ".join(set(t.publishers)) or "none"
        s = ", ".join(set(t.subscribers)) or "none"
        behavior_lines.append(f"• {t.name} ({t.message_type}): pub {p} → sub {s}")

    for s in services_list:
        srv = ", ".join(s.servers) or "none"
        cli = ", ".join(s.clients) or "none"
        behavior_lines.append(f"• Service {s.name} ({s.type}): server {srv} ↔ client {cli}")

    behavior_summary = "**Detected ROS Communication:**\n\n" + "\n".join(behavior_lines) if behavior_lines else "No communication patterns detected."

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


@app.get("/api/graph/{analysis_id}", response_model=GraphResponse)
async def get_communication_graph(analysis_id: str):
    project_dir = TEMP_EXTRACT_DIR / analysis_id
    if not project_dir.is_dir():
        raise HTTPException(404, "Project not found")

    if analysis_id not in analysis_cache:
        analysis_cache[analysis_id] = parse_project(project_dir)

    model = analysis_cache[analysis_id]

    nodes = [GraphNode(id=n.name, label=n.name, type="node") for n in model.nodes]
    edges = []

    for idx, topic in enumerate(model.topics.values()):
        tid = f"t_{idx}"
        nodes.append(GraphNode(id=tid, label=topic.name, type="topic"))
        for p in set(topic.publishers):
            edges.append(GraphEdge(id=f"p_{p}_{tid}", source=p, target=tid, label="pub"))
        for s in set(topic.subscribers):
            edges.append(GraphEdge(id=f"s_{tid}_{s}", source=tid, target=s, label="sub"))

    for idx, srv in enumerate(model.services.values()):
        sid = f"srv_{idx}"
        nodes.append(GraphNode(id=sid, label=srv.name, type="service"))
        for server in srv.servers:
            edges.append(GraphEdge(id=f"srv_s_{server}_{sid}", source=server, target=sid, label="provides"))
        for client in srv.clients:
            edges.append(GraphEdge(id=f"srv_c_{client}_{sid}", source=client, target=sid, label="calls"))

    return GraphResponse(nodes=nodes, edges=edges)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")