# backend/app/parsers.py
"""
ROS project parsers for Python, C++, and launch files
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


# ============================================
# ROS MODEL
# ============================================

class RosModel:
    """
    Container for parsed ROS project data
    """
    
    def __init__(self):
        self.nodes: List[NodeInfo] = []
        self.node_names: Set[str] = set()
        self.topics: Dict[str, TopicInfo] = {}
        self.services: Dict[str, ServiceInfo] = {}
        self.parameters: Set[str] = set()
        self.warnings: List[str] = []
    
    def add_node(self, name: str, file_path: Path, base_path: Path):
        """
        Add a ROS node with deduplication logic
        
        Priority: Source files > Launch files
        """
        try:
            clean_file = str(file_path.relative_to(base_path))
        except ValueError:
            clean_file = file_path.name
        
        is_launch = file_path.suffix.lower() in ('.launch', '.xml')
        
        if name in self.node_names:
            existing = next((n for n in self.nodes if n.name == name), None)
            if existing:
                existing_is_launch = existing.file.lower().endswith(('.launch', '.xml'))
                
                # Launch duplicate → ignore
                if is_launch:
                    return
                
                # Source duplicate → warn and keep first
                if not is_launch:
                    self.warnings.append(
                        f"Duplicate node '{name}' in source files: "
                        f"using {existing.file}, ignoring {clean_file}"
                    )
                    return
        
        # Add new unique node
        self.node_names.add(name)
        self.nodes.append(NodeInfo(name=name, file=clean_file))
        logger.debug(f"Added node: {name} from {clean_file}")
    
    def add_pub(self, topic: str, msg_type: str, node: str):
        """Add publisher to topic"""
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
        """Add subscriber to topic"""
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
        """Add service server or client"""
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
        """Add parameter"""
        self.parameters.add(param)


# ============================================
# FILE FILTERING
# ============================================

def is_relevant_source_file(path: Path) -> bool:
    """
    Check if file should be parsed
    
    Args:
        path: File path to check
        
    Returns:
        bool: True if file is relevant for parsing
    """
    path_str = str(path).lower()
    
    # Check ignored paths
    for ignored in settings.IGNORED_PATHS:
        if ignored in path_str:
            return False
    
    # Check if it's a generated file
    if path.suffix == '.py':
        try:
            content = path.read_text(errors="ignore", encoding="utf-8")
            if "generated from catkin/cmake/template" in content:
                return False
        except:
            pass
    
    # Check extension
    return path.suffix.lower() in settings.RELEVANT_EXTENSIONS


# ============================================
# PYTHON PARSER
# ============================================

class ROSASTVisitor(ast.NodeVisitor):
    """
    AST visitor for parsing Python ROS nodes
    """
    
    def __init__(self, model: RosModel, filepath: Path, base_path: Path):
        self.model = model
        self.filepath = filepath
        self.base_path = base_path
        self.current_node: Optional[str] = None
        self.pubs = []
        self.subs = []
        self.services = []
        self.params = []
        self.has_rate = False
        self.has_try = False
    
    def visit_Call(self, node):
        """Visit function calls to detect ROS API usage"""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "rospy":
                attr = node.func.attr
                
                # Node initialization
                if attr == "init_node":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        name = node.args[0].value
                        if isinstance(name, str):
                            self.current_node = name
                            self.model.add_node(name, self.filepath, self.base_path)
                
                # Publisher
                elif attr == "Publisher":
                    if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                        topic = node.args[0].value
                        msg_type = self._get_type(node.args[1])
                        self.pubs.append((topic, msg_type))
                
                # Subscriber
                elif attr == "Subscriber":
                    if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                        topic = node.args[0].value
                        msg_type = self._get_type(node.args[1])
                        self.subs.append((topic, msg_type))
                
                # Service Server
                elif attr == "Service":
                    if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                        srv = node.args[0].value
                        typ = self._get_type(node.args[1])
                        self.services.append((srv, typ, True))
                
                # Service Client
                elif attr == "ServiceProxy":
                    if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                        srv = node.args[0].value
                        typ = self._get_type(node.args[1])
                        self.services.append((srv, typ, False))
                
                # Parameters
                elif attr in ("get_param", "set_param", "has_param", "delete_param"):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        self.params.append(node.args[0].value)
                
                # Rate (for warning detection)
                elif attr == "Rate":
                    self.has_rate = True
        
        self.generic_visit(node)
    
    def visit_Try(self, node):
        """Detect try/except blocks"""
        self.has_try = True
        self.generic_visit(node)
    
    def _get_type(self, node) -> str:
        """Extract type name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = node.value.id if isinstance(node.value, ast.Name) else "?"
            return f"{base}.{node.attr}"
        return "unknown"
    
    def finalize(self):
        """Process collected data after visiting"""
        if not self.current_node:
            return
        
        # Add publishers/subscribers
        for t, m in self.pubs:
            self.model.add_pub(t, m, self.current_node)
        for t, m in self.subs:
            self.model.add_sub(t, m, self.current_node)
        
        # Add services
        for s, t, server in self.services:
            self.model.add_service(s, t, self.current_node, server)
        
        # Add parameters
        for p in self.params:
            self.model.add_param(p)
        
        # Check best practices
        if not self.has_rate:
            self.model.warnings.append(
                f"[{self.current_node}] Missing rospy.Rate → possible high CPU usage"
            )
        if not self.has_try:
            self.model.warnings.append(
                f"[{self.current_node}] No try/except blocks → fragile error handling"
            )


def parse_python_ros_file(filepath: Path, model: RosModel, base_path: Path):
    """
    Parse Python ROS file using AST
    
    Args:
        filepath: Path to Python file
        model: RosModel to populate
        base_path: Base project path
    """
    if not is_relevant_source_file(filepath):
        return
    
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(filepath))
        visitor = ROSASTVisitor(model, filepath, base_path)
        visitor.visit(tree)
        visitor.finalize()
        logger.debug(f"Parsed Python file: {filepath.name}")
    except SyntaxError as e:
        logger.warning(f"Syntax error in {filepath.name}: {str(e)}")
    except Exception as e:
        model.warnings.append(f"Python parse error in {filepath.name}: {str(e)}")
        logger.error(f"Error parsing {filepath.name}: {str(e)}")


# ============================================
# C++ PARSER
# ============================================

def parse_cpp_ros_file(filepath: Path, model: RosModel, base_path: Path):
    """
    Parse C++ ROS file using regex
    
    Args:
        filepath: Path to C++ file
        model: RosModel to populate
        base_path: Base project path
    """
    if filepath.suffix.lower() not in ('.cpp', '.c', '.h', '.hpp'):
        return
    
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        
        # Detect ros::init calls
        for match in re.finditer(r'ros::init\s*\([^,]+,\s*["\']([^"\']+)["\']', content):
            name = match.group(1)
            model.add_node(name, filepath, base_path)
            logger.debug(f"Found C++ node: {name} in {filepath.name}")
        
    except Exception as e:
        logger.error(f"Error parsing C++ file {filepath.name}: {str(e)}")


# ============================================
# LAUNCH FILE PARSER
# ============================================

def parse_launch_file(filepath: Path, model: RosModel, base_path: Path):
    """
    Parse ROS launch file (XML)
    
    Args:
        filepath: Path to launch file
        model: RosModel to populate
        base_path: Base project path
    """
    if not filepath.name.lower().endswith(('.launch', '.xml')):
        return
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Find all <node> elements
        for node_elem in root.findall('.//node'):
            name = node_elem.get('name')
            if name:
                model.add_node(name, filepath, base_path)
                logger.debug(f"Found launch node: {name} in {filepath.name}")
        
    except ET.ParseError as e:
        logger.warning(f"XML parse error in {filepath.name}: {str(e)}")
    except Exception as e:
        model.warnings.append(f"Launch parse error {filepath.name}: {str(e)}")
        logger.error(f"Error parsing launch file {filepath.name}: {str(e)}")


# ============================================
# MAIN PARSER
# ============================================

def parse_project(project_dir: Path) -> RosModel:
    """
    Parse entire ROS project
    
    Strategy:
    1. Parse source files first (Python, C++)
    2. Parse launch files last (deduplication handled by model)
    
    Args:
        project_dir: Root directory of project
        
    Returns:
        RosModel: Populated model with all detected ROS components
    """
    logger.info(f"Starting project parsing: {project_dir}")
    model = RosModel()
    
    # Find actual root (handle single-folder ZIPs)
    contents = list(project_dir.iterdir())
    base_path = contents[0] if len(contents) == 1 and contents[0].is_dir() else project_dir
    
    # Phase 1: Parse source files
    source_extensions = {'.py', '.cpp', '.c', '.h', '.hpp'}
    source_files = []
    
    for ext in source_extensions:
        source_files.extend(base_path.rglob(f'*{ext}'))
    
    source_files = [f for f in source_files if is_relevant_source_file(f)]
    source_files.sort(key=str)
    
    logger.info(f"Found {len(source_files)} source files")
    
    for file in source_files:
        if file.suffix.lower() == '.py':
            parse_python_ros_file(file, model, base_path)
        else:
            parse_cpp_ros_file(file, model, base_path)
    
    # Phase 2: Parse launch files
    launch_files = list(base_path.rglob('*.launch')) + list(base_path.rglob('*.xml'))
    launch_files = [f for f in launch_files if 'package.xml' not in f.name.lower()]
    launch_files.sort(key=str)
    
    logger.info(f"Found {len(launch_files)} launch files")
    
    for file in launch_files:
        parse_launch_file(file, model, base_path)
    
    logger.info(f"Parsing complete - Nodes: {len(model.nodes)}, Topics: {len(model.topics)}, Warnings: {len(model.warnings)}")
    
    return model