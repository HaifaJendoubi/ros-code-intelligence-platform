# backend/app/main.py

import uuid
import zipfile
import shutil
import aiofiles
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ────────────────────────────────────────────────
# Modèles Pydantic
# ────────────────────────────────────────────────

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


class AnalysisResponse(BaseModel):
    status: str
    analysis_id: str
    nodes: List[NodeInfo]
    topics: List[TopicInfo]
    metrics: Dict[str, int]
    behavior_summary: str
    warnings: List[str]


# ────────────────────────────────────────────────
# FastAPI + CORS
# ────────────────────────────────────────────────

app = FastAPI(
    title="ROS Code Intelligence Platform",
    description="Analyse statique de code ROS - détection nœuds/topics/pubs/subs",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_UPLOAD_DIR = Path("uploads")
TEMP_EXTRACT_DIR = Path("extracted_projects")

BASE_UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_EXTRACT_DIR.mkdir(exist_ok=True)


# ────────────────────────────────────────────────
# Arborescence fichiers
# ────────────────────────────────────────────────

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
                '.py', '.cpp', '.c', '.h', '.hpp', '.launch', '.xml', '.yaml', '.yml'
            )):
                node.children.append(child)

    return node


# ────────────────────────────────────────────────
# Modèle ROS + anti-doublons
# ────────────────────────────────────────────────

class RosModel:
    def __init__(self):
        self.nodes: List[NodeInfo] = []
        self.node_names: Set[str] = set()           # clé : évite doublons
        self.topics: Dict[str, TopicInfo] = {}
        self.warnings: List[str] = []

    def add_node(self, name: str, file: str):
        if name in self.node_names:
            self.warnings.append(f"Nœud dupliqué détecté : '{name}' dans {file}")
            return
        self.node_names.add(name)
        self.nodes.append(NodeInfo(name=name, file=file))

    def add_pub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(name=topic, message_type=msg_type, publishers=[], subscribers=[])
        self.topics[topic].publishers.append(node)

    def add_sub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(name=topic, message_type=msg_type, publishers=[], subscribers=[])
        self.topics[topic].subscribers.append(node)


# ────────────────────────────────────────────────
# Filtre fichiers pertinents
# ────────────────────────────────────────────────

def is_relevant_source_file(path: Path) -> bool:
    name = path.name.lower()
    path_str = str(path).lower()

    # Ignorer build/devel/install/log/cache
    if any(x in path_str for x in ['/devel/', '/install/', '/build/', '/log/', '__pycache__', '.pyc', '.pyo']):
        return False

    # Ignorer wrappers catkin
    try:
        content = path.read_text(errors='ignore')
        if 'generated from catkin/cmake/template/script.py.in' in content:
            return False
    except:
        pass

    # Accepter extensions ROS
    return name.endswith(('.py', '.cpp', '.c', '.h', '.hpp', '.launch', '.xml', '.yaml', '.yml'))


# ────────────────────────────────────────────────
# Parser ROS (rospy) - version robuste
# ────────────────────────────────────────────────

def parse_python_ros_file(filepath: Path, model: RosModel):
    if not is_relevant_source_file(filepath):
        return

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERREUR] Lecture {filepath}: {e}")
        return

    print(f"[PARSE] {filepath.name}")

    current_node = None

    # Détection nœud
    node_match = re.search(r'rospy\s*\.\s*init_node\s*\(\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if node_match:
        current_node = node_match.group(1)
        model.add_node(current_node, filepath.name)
        print(f"  → Nœud : '{current_node}'")

    # Publishers (très tolérant)
    for match in re.finditer(
        r'(?:rospy\s*\.\s*)?Publisher\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^,\s\)]+)',
        content, re.IGNORECASE
    ):
        topic, msg_type = match.groups()
        topic = topic.strip()
        msg_type = msg_type.strip()
        # Normalisation type
        if not msg_type.startswith('std_msgs/'):
            msg_type = f"std_msgs/{msg_type}"
        if current_node:
            model.add_pub(topic, msg_type, current_node)
            print(f"  → Pub → '{topic}' ({msg_type})")

    # Subscribers
    for match in re.finditer(
        r'(?:rospy\s*\.\s*)?Subscriber\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^,\s\)]+)',
        content, re.IGNORECASE
    ):
        topic, msg_type = match.groups()
        topic = topic.strip()
        msg_type = msg_type.strip()
        if not msg_type.startswith('std_msgs/'):
            msg_type = f"std_msgs/{msg_type}"
        if current_node:
            model.add_sub(topic, msg_type, current_node)
            print(f"  → Sub → '{topic}' ({msg_type})")

    # Warning absence Rate
    if current_node and "while not rospy.is_shutdown()" in content and "rospy.Rate" not in content:
        model.warnings.append(
            f"[BEST PRACTICE] Nœud '{current_node}' ({filepath.name}) : boucle while sans rospy.Rate → CPU élevé"
        )


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "service": "ros-code-intelligence"}


@app.post("/api/upload-zip/", response_model=UploadResponse, tags=["Upload"])
async def upload_and_extract_zip(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Seuls les fichiers .zip sont acceptés")

    analysis_id = uuid.uuid4().hex[:12]
    zip_path = BASE_UPLOAD_DIR / f"{analysis_id}_{file.filename}"

    async with aiofiles.open(zip_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    extract_folder = TEMP_EXTRACT_DIR / analysis_id
    extract_folder.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for member in z.namelist():
                target = extract_folder / member
                if not target.resolve().is_relative_to(extract_folder.resolve()):
                    raise HTTPException(400, "Archive invalide : path traversal")
            z.extractall(extract_folder)
    except Exception as e:
        shutil.rmtree(extract_folder, ignore_errors=True)
        raise HTTPException(400, f"Échec extraction : {str(e)}")

    zip_path.unlink(missing_ok=True)

    file_count = sum(1 for _ in extract_folder.rglob("*") if _.is_file())

    return UploadResponse(
        status="success",
        analysis_id=analysis_id,
        original_filename=file.filename,
        extracted_to=str(extract_folder),
        file_count=file_count,
        message="Archive uploadée et extraite"
    )


@app.get("/api/project-tree/{analysis_id}", response_model=TreeResponse, tags=["Project"])
async def get_project_tree(analysis_id: str):
    project_dir = TEMP_EXTRACT_DIR / analysis_id
    if not project_dir.is_dir():
        raise HTTPException(404, "Projet non trouvé")

    contents = list(project_dir.iterdir())
    root_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else project_dir

    tree = build_file_tree(root_dir)

    return TreeResponse(
        status="ok",
        analysis_id=analysis_id,
        root_name=root_dir.name,
        tree=tree
    )


@app.get("/api/analyze/{analysis_id}", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_project(analysis_id: str):
    project_dir = TEMP_EXTRACT_DIR / analysis_id
    if not project_dir.is_dir():
        raise HTTPException(404, "Projet non trouvé")

    model = RosModel()

    # Parsing filtré
    for py_file in project_dir.rglob("*.py"):
        parse_python_ros_file(py_file, model)

    topics_list = list(model.topics.values())

    metrics = {
        "nodes_count": len(model.nodes),
        "topics_count": len(topics_list),
        "publishers_count": sum(len(set(t.publishers)) for t in topics_list),  # unique !
        "subscribers_count": sum(len(set(t.subscribers)) for t in topics_list),
    }

    # Behavior summary amélioré
    behavior_summary = "Aucun comportement clair détecté."
    if len(model.nodes) >= 2 and len(topics_list) >= 1:
        t = topics_list[0]
        unique_pubs = set(t.publishers)
        unique_subs = set(t.subscribers)

        if len(unique_pubs) >= 1 and len(unique_subs) >= 1:
            pub_str = " et ".join(unique_pubs) if len(unique_pubs) > 1 else list(unique_pubs)[0]
            sub_str = " et ".join(unique_subs) if len(unique_subs) > 1 else list(unique_subs)[0]

            behavior_summary = (
                f"**Comportement détecté : pattern talker/listener classique**\n\n"
                f"• Nœud(s) émetteur(s) : {pub_str} publie(nt) des messages de type {t.message_type}\n"
                f"  sur le topic **'{t.name}'**\n"
                f"• Nœud(s) récepteur(s) : {sub_str} s’abonne(nt) et traite(nt) les messages\n\n"
                "→ Communication unidirectionnelle simple : diffusion périodique de données d’un nœud vers un ou plusieurs autres."
            )

    return AnalysisResponse(
        status="analyzed",
        analysis_id=analysis_id,
        nodes=model.nodes,
        topics=topics_list,
        metrics=metrics,
        behavior_summary=behavior_summary,
        warnings=model.warnings
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )