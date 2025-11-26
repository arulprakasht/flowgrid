# FlowGrid AI Logistics Platform

## Overview
FlowGrid is a scalable, agentic logistics simulation and business platform powered by Python, Streamlit, and Redis. It features real-time multi-agent coordination, predictive optimization, dynamic pricing, and advanced business analytics.

## Features
- AI-powered vehicle, dispatch, and customer agents
- Real-time map visualization (pydeck, OSM)
- Weather, traffic, and demand simulation
- Dynamic vehicle assignment and route optimization
- Predictive business metrics and analytics
- Fleet health, revenue, and customer satisfaction tracking
- Multi-agent memory, reasoning, and collaboration
- Fault tolerance and Redis error handling
- Extensible for LLM integration (Ollama, etc.)

## Requirements
- Python 3.8+
- Redis server running locally (default: localhost:6379)
- Streamlit
- pandas, numpy, pydeck

### How to Run Redis Locally
- **Docker (recommended, one-liner):**
  ```sh
  docker run -d --name flowgrid-redis -p 6379:6379 redis:7-alpine
  ```
- **macOS:**
  ```sh
  brew install redis
  brew services start redis
  # Or run manually:
  redis-server
  ```
- **Linux (Debian/Ubuntu):**
  ```sh
  sudo apt-get update
  sudo apt-get install redis-server
  redis-server
  ```
- **Windows:**
  - Use [Memurai](https://www.memurai.com/) or [Redis for Windows](https://github.com/microsoftarchive/redis/releases)
  - Start Redis from installed location.

- By default, Redis runs on `localhost:6379`. No password is required for local development.

### Project Setup
1. Create project folder:
   ```sh
   mkdir ~/flowgrid && cd ~/flowgrid
   ```
2. Create and activate Python environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```sh
   pip install redis streamlit pandas numpy pydeck networkx matplotlib
   ```

## Quickstart
1. Install dependencies:
   ```sh
   pip install streamlit redis pandas numpy pydeck
   ```
2. Start Redis server locally:
   ```sh
   redis-server
   ```
3. Run the app:
   ```sh
   streamlit run main.py
   ```

## Usage Notes
- Do not run `main.py` directly with `python main.py`. Always use `streamlit run main.py`.
- The dashboard provides live metrics, agent intelligence, and business analytics.
- The system is extensible for verticals like rideshare, robotics, and more.

## Redis Architecture Highlights
- Uses Redis for agent memory, state management, pub/sub messaging, and analytics.
- Designed for horizontal scalability, real-time coordination, and production deployment.
- All agent state and event logs are stored in Redis for durability and analytics.

## License
MIT