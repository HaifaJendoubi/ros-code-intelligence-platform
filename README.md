Step 1: Prepare your project folder
Make sure your folder (ros-code-intelligence-platform) looks like this:
textros-code-intelligence-platform/
├── backend/
│   ├── app/
│   │   └── main.py
│   └── requirements.txt          ← you can create this
├── frontend/
│   ├── src/
│   │   └── App.tsx
│   ├── package.json
│   └── ... (other vite/react files)
├── README.md                     ← we will create this
└── .gitignore                    ← important!
Step 2: Create .gitignore (very important)
Create a file called .gitignore in the root folder and paste this content (prevents uploading useless files like node_modules, cache, etc.):
gitignore# Python / Backend
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
*.egg-info/
dist/
build/
*.egg

# Node / Frontend
node_modules/
npm-debug.log
yarn-debug.log
yarn-error.log
dist/
build/
*.log

# Cache & temp
analysis_cache/
uploads/
extracted_projects/
.DS_Store
Thumbs.db

# Editor & OS files
.vscode/
.idea/
*.swp
*.swo
Step 3: Create requirements.txt for backend (optional but professional)
In backend/ folder, create requirements.txt with:
txtfastapi
uvicorn
aiofiles
pydantic
Step 4: Initialize Git & push to GitHub
Open a terminal (or PowerShell) in your project root folder:
Bash# 1. Go to your project folder
cd C:\Users\Pc\ros-code-intelligence-platform

# 2. Initialize git (only once)
git init

# 3. Add all files
git add .

# 4. First commit
git commit -m "Initial commit: ROS Code Intelligence Platform - full project with frontend & backend"

# 5. Create GitHub repository (do this in browser first!)
#    → go to github.com → New repository
#    → Name: ros-code-intelligence-platform
#    → Do NOT initialize with README or .gitignore (we already have them)
#    → Create repository

# 6. Link your local project to the GitHub repo
#    Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/ros-code-intelligence-platform.git

# 7. Push to main branch
git branch -M main
git push -u origin main
If asked for login:

Use your GitHub username
For password: use a Personal Access Token (not your real password)
How to create token: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token → give "repo" scope → copy token


Step 5: Professional README.md (copy-paste this)
Create README.md in the root folder and paste this content:
Markdown# ROS Code Intelligence Platform

Web-based static analysis tool for ROS 1 projects.  
Upload a ZIP archive → get structured file tree, key ROS metrics, communication behavior summary, best-practice warnings, and interactive communication graph.

https://github.com/YOUR_USERNAME/ros-code-intelligence-platform

## Features

- ZIP upload & automatic project extraction
- Structured, navigable file tree view (react-arborist)
- ROS concept extraction:
  - Nodes (from source & launch files, deduplicated)
  - Topics + message types
  - Publishers & Subscribers
  - Services (servers & clients)
  - Parameters
- Behavior summary (pub → sub communication flow)
- Code quality & best practices warnings
  - Missing `rospy.Rate` → possible high CPU
  - No `try/except` blocks → fragile error handling
  - Duplicate node names
- Interactive communication graph (React Flow)
- Clean, modern UI (Tailwind + dark theme)

## Architecture

- **Frontend**: React 19 + Vite + Tailwind CSS + react-arborist + @xyflow/react
- **Backend**: FastAPI (Python) + AST parsing (.py) + regex (.cpp) + ElementTree (.launch/.xml)
- **Data Flow**:
  1. User uploads ZIP → backend extracts to temp folder
  2. Parse source files **first** (.py, .cpp, .h, .hpp)
  3. Parse launch files **last** (.launch, .xml) → only add missing nodes
  4. Cache results → serve tree / metrics / graph

## Setup & Run (Local)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
Frontend
Bashcd frontend
npm install
npm run dev
→ Open http://localhost:5173
Project Structure
textros-code-intelligence-platform/
├── backend/
│   ├── app/
│   │   └── main.py           # FastAPI + parsing logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── App.tsx           # Main React component
│   ├── package.json
│   └── vite.config.ts
├── README.md
└── .gitignore
Evaluation Highlights

Robotics & ROS Understanding — full parsing of nodes/topics/pub/sub/services/parameters/launch files
Code Interpretation — AST + regex + XML parsing, deduplication logic (source > launch)
Metrics & Analysis — complete counts + behavior flow summary
UI/UX — clean tabs, metrics cards, responsive dark theme, interactive graph
Code Quality — modular, deduplicated, warnings for common ROS issues

Test Packages Used

Camera system package
→ Nodes: 4, Topics: 2, Publishers: 2, Subscribers: 1
Talker-Listener package
→ Nodes: 2, Topics: 1, Publishers: 1, Subscribers: 1

Author
Haifa
Tunis, Tunisia
January 31, 2026
