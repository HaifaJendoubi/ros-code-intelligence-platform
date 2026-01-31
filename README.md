# 🚀 ROS Code Intelligence Platform

Web-based **static analysis tool** for ROS 1 projects.  
Upload a ZIP archive to get a **structured file tree**, **key ROS metrics**, **communication behavior summary**, **best-practice warnings**, and an **interactive communication graph**.

🔗 [GitHub Repository](https://github.com/YOUR_USERNAME/ros-code-intelligence-platform)

---

## ✨ Features

- 📦 ZIP upload & automatic project extraction
- 🌳 Navigable file tree view (react-arborist)
- 🤖 ROS concept extraction:
  - Nodes (from source & launch files, deduplicated)
  - Topics + message types
  - Publishers & Subscribers
  - Services (servers & clients)
  - Parameters
- 🔄 Communication flow summary (pub → sub)
- ⚠️ Code quality & best-practice warnings:
  - Missing `rospy.Rate` → high CPU risk
  - Missing `try/except` → fragile error handling
  - Duplicate node names
- 🖼 Interactive communication graph (React Flow)
- 🎨 Clean, modern UI (Tailwind + dark theme)

---

## 🏗 Architecture

- **Frontend**: React 19 + Vite + Tailwind CSS + react-arborist + @xyflow/react  
- **Backend**: FastAPI (Python) + AST parsing (.py) + regex (.cpp) + ElementTree (.launch/.xml)  

### Data Flow
1. User uploads ZIP → backend extracts to temp folder  
2. Parse **source files first** (.py, .cpp, .h, .hpp)  
3. Parse **launch files last** (.launch, .xml) → only add missing nodes  
4. Cache results → serve **tree / metrics / graph**

### Example Architecture Diagram
![Architecture Example](docs/architecture.png)  
> Replace with your real screenshot of frontend/backend architecture

---
```bash
## 🗂 Project Structure

ros-code-intelligence-platform/
├── backend/
│ ├── app/
│ │ └── main.py # FastAPI + parsing logic
│ └── requirements.txt
├── frontend/
│ ├── src/
│ │ └── App.tsx # Main React component
│ ├── package.json
│ └── vite.config.ts
├── README.md
└── .gitignore


---

## ⚙️ Setup & Run (Local)

### Backend

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
Frontend
cd frontend
npm install
npm run dev
# Open http://localhost:5173
🔗 Git Setup & Push
# Initialize git
git init
git add .
git commit -m "Initial commit: ROS Code Intelligence Platform"

# Link to GitHub repo
git remote add origin https://github.com/YOUR_USERNAME/ros-code-intelligence-platform.git
git branch -M main
git push -u origin main
For authentication, use your GitHub username and a Personal Access Token with repo scope.

📊 Evaluation Highlights
Robotics & ROS Understanding — parsing nodes, topics, publishers/subscribers, services, parameters, and launch files

Code Interpretation — AST + regex + XML parsing, deduplication logic (source > launch)

Metrics & Analysis — counts + behavior flow summary

UI/UX — clean tabs, metrics cards, responsive dark theme, interactive graph

Code Quality — modular, deduplicated, warnings for common ROS issues

🔬 Test Packages
Camera system package → Nodes: 4, Topics: 2, Publishers: 2, Subscribers: 1

Talker-Listener package → Nodes: 2, Topics: 1, Publishers: 1, Subscribers: 1

Example Screenshots


Replace these with your actual screenshots

📝 Author
Haifa
Tunis, Tunisia
📅 January 31, 2026
