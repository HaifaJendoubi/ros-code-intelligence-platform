# backend/app/parsers.py
"""
ROS project parser - version adaptée pour détecter chatter + talker/listener
Évite UnboundLocalError et gère mieux les doublons de nœuds
"""

import ast
import re
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import Set, List, Dict, Optional

from .models import NodeInfo, TopicInfo, ServiceInfo
from .config import settings

logger = logging.getLogger(__name__)


class RosModel:
    def __init__(self):
        self.nodes: List[NodeInfo] = []
        self.node_names: Set[str] = set()
        self.topics: Dict[str, TopicInfo] = {}
        self.services: Dict[str, ServiceInfo] = {}
        self.parameters: Set[str] = set()
        self.warnings: List[str] = []

    def add_node(self, name: str, file_path: Path, base_path: Path):
        try:
            clean_file = str(file_path.relative_to(base_path))
        except ValueError:
            clean_file = file_path.name

        is_launch = file_path.suffix.lower() in ('.launch', '.xml')

        if name in self.node_names:
            existing = next((n for n in self.nodes if n.name == name), None)
            if existing:
                # Cas fréquent dans les tutos : talker et talker_timer
                if "timer" in clean_file.lower() and "talker" in name.lower():
                    self.nodes.append(NodeInfo(name=f"{name}_timer", file=clean_file))
                    self.node_names.add(f"{name}_timer")
                    logger.debug(f"Ajout variante timer: {name}_timer")
                    return
                # Sinon on garde le premier (généralement le principal)
                self.warnings.append(
                    f"Duplicate node '{name}' → using {existing.file}, ignoring {clean_file}"
                )
                return

        self.node_names.add(name)
        self.nodes.append(NodeInfo(name=name, file=clean_file))
        logger.debug(f"Added node: {name} from {clean_file}")

    def add_pub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(
                name=topic,
                message_type=msg_type or "unknown",
                publishers=[],
                subscribers=[]
            )
        if node not in self.topics[topic].publishers:
            self.topics[topic].publishers.append(node)

    def add_sub(self, topic: str, msg_type: str, node: str):
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(
                name=topic,
                message_type=msg_type or "unknown",
                publishers=[],
                subscribers=[]
            )
        if node not in self.topics[topic].subscribers:
            self.topics[topic].subscribers.append(node)

    def add_service(self, service: str, srv_type: str, node: str, is_server: bool):
        if service not in self.services:
            self.services[service] = ServiceInfo(
                name=service,
                type=srv_type or "unknown",
                servers=[],
                clients=[]
            )
        target = self.services[service].servers if is_server else self.services[service].clients
        if node not in target:
            target.append(node)

    def add_param(self, param: str):
        self.parameters.add(param)


def is_relevant_source_file(path: Path) -> bool:
    path_str = str(path).lower()
    for ignored in settings.IGNORED_PATHS:
        if ignored in path_str:
            return False

    # Fichiers non-ROS classiques (évite les erreurs)
    skip_keywords = {"lexer", "parser", "buchi", "promela", "ltl", "spin", "modelcheck", "ts", "discrete", "product"}
    if any(kw in path.stem.lower() for kw in skip_keywords):
        return False

    if path.suffix == '.py':
        try:
            content = path.read_text(errors="ignore", encoding="utf-8")
            if "generated from catkin/cmake/template" in content:
                return False
        except:
            pass

    return path.suffix.lower() in settings.RELEVANT_EXTENSIONS


class ROSASTVisitor(ast.NodeVisitor):
    def __init__(self, model: RosModel, filepath: Path, base_path: Path):
        self.model = model
        self.filepath = filepath
        self.base_path = base_path
        self.current_node: Optional[str] = None
        self.pubs = []
        self.subs = []
        self.services = []
        self.action_clients = []
        self.params = []
        self.has_rate = False

    def _extract_string_value(self, node) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if hasattr(ast, 'Str') and isinstance(node, ast.Str):
            return node.s
        return None

    def _get_type(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.insert(0, current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.insert(0, current.id)
            return ".".join(parts)
        return "unknown"

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Attribute):
            self.generic_visit(node)
            return

        # Lecture IMMÉDIATE de attr → évite UnboundLocalError
        attr_name = node.func.attr
        value = node.func.value

        # rospy.XXX
        if isinstance(value, ast.Name) and value.id == "rospy":
            if attr_name == "init_node":
                if node.args:
                    name = self._extract_string_value(node.args[0])
                    if name:
                        self.current_node = name
                        self.model.add_node(name, self.filepath, self.base_path)

            elif attr_name == "Publisher":
                if len(node.args) >= 2:
                    topic = self._extract_string_value(node.args[0])
                    if topic:
                        msg_type = self._get_type(node.args[1])
                        self.pubs.append((topic, msg_type))

            elif attr_name == "Subscriber":
                if len(node.args) >= 2:
                    topic = self._extract_string_value(node.args[0])
                    if topic:
                        msg_type = self._get_type(node.args[1])
                        self.subs.append((topic, msg_type))

            elif attr_name == "Rate":
                self.has_rate = True

            elif attr_name in ("get_param", "set_param"):
                if node.args:
                    param = self._extract_string_value(node.args[0])
                    if param:
                        self.params.append(param)

        # actionlib → on le garde en warning mais pas en service pour l'instant
        elif attr_name == "SimpleActionClient" and isinstance(value, ast.Attribute):
            if len(node.args) >= 2:
                action_name = self._extract_string_value(node.args[0])
                if action_name:
                    self.model.warnings.append(
                        f"Action client détecté mais non compté comme service : {action_name}"
                    )

        self.generic_visit(node)

    def finalize(self):
        if not self.current_node:
            return

        has_comms = bool(self.pubs or self.subs)

        for t, m in self.pubs:
            self.model.add_pub(t, m, self.current_node)
        for t, m in self.subs:
            self.model.add_sub(t, m, self.current_node)
        for s, t, is_server in self.services:
            self.model.add_service(s, t, self.current_node, is_server)
        for p in self.params:
            self.model.add_param(p)

        # Warning Rate seulement si communications détectées
        if has_comms and not self.has_rate:
            self.model.warnings.append(
                f"[{self.current_node}] Pas de rospy.Rate → possible boucle CPU intensive"
            )


def parse_python_ros_file(filepath: Path, model: RosModel, base_path: Path):
    if not is_relevant_source_file(filepath):
        return

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        # Petit fix Python 2/3 print
        content = re.sub(r'\bprint\s+"([^"]*)"', r'print("\1")', content)
        content = re.sub(r"\bprint\s+'([^']*)'", r"print('\1')", content)

        tree = ast.parse(content, filename=str(filepath))
        visitor = ROSASTVisitor(model, filepath, base_path)
        visitor.visit(tree)
        visitor.finalize()

    except SyntaxError as e:
        model.warnings.append(f"SyntaxError {filepath.name}: {str(e)}")
    except Exception as e:
        model.warnings.append(f"Parse error {filepath.name}: {str(e)}")


# C++ parser (très basique - on peut l'améliorer plus tard)
def parse_cpp_ros_file(filepath: Path, model: RosModel, base_path: Path):
    if filepath.suffix.lower() not in ('.cpp', '.c', '.h', '.hpp'):
        return
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'ros::init\s*\([^,]+,\s*["\']([^"\']+)["\']', content):
            model.add_node(m.group(1), filepath, base_path)
    except:
        pass


# Launch parser
def parse_launch_file(filepath: Path, model: RosModel, base_path: Path):
    if not filepath.name.lower().endswith(('.launch', '.xml')):
        return
    try:
        tree = ET.parse(filepath)
        for node in tree.findall(".//node"):
            name = node.get("name")
            if name:
                model.add_node(name, filepath, base_path)
    except:
        pass


def parse_project(project_dir: Path) -> RosModel:
    model = RosModel()
    base_path = project_dir

    # Sources
    for ext in ['.py', '.cpp', '.c', '.h', '.hpp']:
        for f in base_path.rglob(f'*{ext}'):
            if ext == '.py':
                parse_python_ros_file(f, model, base_path)
            else:
                parse_cpp_ros_file(f, model, base_path)

    # Launch
    for f in base_path.rglob("*.launch"):
        parse_launch_file(f, model, base_path)
    for f in base_path.rglob("*.xml"):
        if "launch" in f.name.lower():
            parse_launch_file(f, model, base_path)

    return model
