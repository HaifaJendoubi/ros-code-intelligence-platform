# ROS Code Intelligence Platform

Web platform to upload, analyze and visualize ROS (mostly ROS 1 style) project code.

**Status**: In development – 48h assessment implementation

## Features planned / in progress
- ZIP upload of ROS package(s)
- File tree navigation
- Extraction of nodes, topics (pub/sub), services, params from launch + Python code
- Basic communication graph visualization
- Metrics (counts, longest chain)
- Heuristic behavior summary
- Basic ROS best practices checks

## Tech stack
- Backend: Python 3.11+ / FastAPI
- Frontend: React 18+ / Vite / TypeScript
- Visualization: React Flow
- Parsing: Python ast + libcst + regex + xml.etree

## Setup (TBD)

...