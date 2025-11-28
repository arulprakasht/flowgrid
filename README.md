# FlowGrid Logistics — AI Agent for Scalable Real-Time Logistics Optimization

## Overview

**FlowGrid** is a production-ready AI Agent designed to optimize vehicle routing, order assignment, and real-time traffic management for logistics operations. Built with **Streamlit**, **Redis**, and **Python**, it demonstrates how an autonomous agent can scale from a proof-of-concept to a real business solution.

The system uses Redis for real-time state synchronization, enabling seamless communication between the simulation engine and the web dashboard. It features intelligent vehicle assignment, traffic-aware rerouting, and agent-based reasoning for decision-making.

## Key Features

- **Real-Time Vehicle Tracking**: Live map visualization of vehicle positions and routes using pydeck and OpenStreetMap
- **Dynamic Business Metrics**: **Hardcoded values replaced** with dynamic calculations for **Distance Saved** and **Cost per Mile**, demonstrating clear ROI.
- **Interactive Simulation**: **One-click "Reset Simulation"** button to instantly start a new scenario with randomized traffic, proving the system's adaptability.
- **Intelligent Order Assignment**: Dynamic, load-balanced assignment algorithm that considers distance, current vehicle load, and traffic zones
- **Traffic-Aware Rerouting**: Vehicles detect traffic jams and automatically reroute to minimize delays
- **Enhanced Agentic Chat**: Interactive sidebar chat that provides **context-aware responses** based on live metrics, showcasing the AI's business value.
- **Scalable Architecture**: Modular design with clear separation of concerns for easy expansion and maintenance

## Architecture

The application is organized into four main modules:

### 1. `config.py` - Configuration Management
Centralizes all configuration parameters:
- Redis connection details
- Simulation parameters (number of vehicles, orders, grid size)
- Map configuration (Seattle center coordinates, basemap URL)
- Vehicle icon URL

**Usage**: Import configuration constants throughout the application for consistency.

### 2. `simulation.py` - Core Simulation Engine
Handles all business logic for the logistics system:
- **Order Generation**: Creates realistic Seattle-area order distributions
- **Vehicle Assignment**: Implements greedy assignment with traffic penalties
- **Movement Simulation**: Background thread that updates vehicle positions
- **Traffic Rerouting**: Detects and routes around traffic zones
- **Agent Reasoning**: Generates intelligent thoughts based on vehicle memory

**Key Functions**:
- `initialize_simulation()`: Sets up orders and vehicles in Redis
- `assign_order_to_vehicle()`: Assigns orders using a scoring algorithm
- `move_vehicles()`: Background thread for vehicle movement
- `llm_agent_reasoning()`: Generates AI-like reasoning (LLM-ready placeholder)

### 3. `ui.py` - Streamlit Dashboard
Renders the interactive web interface:
- **Map Visualization**: Pydeck-based map with vehicle positions, routes, and traffic zones
- **Metrics Display**: Real-time KPIs (deliveries, active vehicles, distance saved, cost per mile)
- **Agent Sidebar**: Shows AI reasoning for each vehicle and accepts user queries
- **Historical Analytics**: Displays delivery history and performance trends
- **Memory Log**: Shows recent events for each vehicle

### 4. `main.py` - Application Orchestrator
Coordinates all components:
- Initializes traffic simulation parameters
- Starts the background simulation thread
- **Calculates and stores aggregate metrics in Redis** for `ui.py` to retrieve
- Renders the Streamlit UI in a continuous loop

## Installation & Setup

### Prerequisites
- Python 3.8+
- Redis server running locally (or accessible at `localhost:6379`)

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/arulprakasht/flowgrid.git
   cd flowgrid
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure Redis is running**:
   ```bash
   redis-server
   ```
   
   Or, if using Docker:
   ```bash
   docker run -d -p 6379:6379 redis:latest
   ```

4. **Run the application**:
   ```bash
   streamlit run main.py
   ```

5. **Access the dashboard**:
   Open your browser and navigate to `http://localhost:8501`

## How It Works

### Simulation Flow

1. **Initialization** (`main.py`):
   - Traffic parameters are set (random traffic zone and step)
   - Orders are generated across the Seattle grid
   - Vehicles are initialized at the depot

2. **Order Assignment** (`simulation.py`):
   - Each order is assigned to the best vehicle using a scoring function
   - Score = Distance + Route Length + Traffic Penalty
   - Assignments are stored in Redis

3. **Vehicle Movement** (`simulation.py`):
   - Background thread runs `move_vehicles()` continuously
   - Each vehicle follows its assigned route step-by-step
   - When approaching the traffic zone, vehicles reroute

4. **Dashboard Updates** (`ui.py`):
   - Streamlit refreshes periodically, pulling latest state from Redis
   - Map updates with vehicle positions
   - Metrics are recalculated in real-time
   - Agent reasoning is generated based on vehicle memory

### Redis Data Structure

The application uses Redis hashes and lists for state management:

```
vehicle:{v_id}
  - pos_x: Current X position
  - pos_y: Current Y position
  - route: JSON array of (x, y) coordinates
  - delivered: Count of deliveries
  - rerouting: Boolean flag
  - delivery_time_{d}: Timestamp of delivery d
  - delivery_miles_{d}: Miles traveled for delivery d

vehicle:{v_id}:memory
  - List of JSON objects: {"time": timestamp, "event": "description"}

metrics
  - avg_delivery_time: Average time for a delivery
  - avg_delivery_miles: Average miles per delivery
  - total_deliveries_computed: Total deliveries completed
  - total_miles: Cumulative distance traveled
```

## Scalability Considerations

### Current Capabilities (Proof-of-Concept)
- Single-threaded simulation (one background thread)
- All state in a single Redis instance
- Real-time updates via Redis pub/sub
- Modular architecture for easy expansion

### Scaling Strategies for Production

1. **Distributed Simulation**:
   - Use a task queue (Celery, RQ) to distribute vehicle movement across multiple workers
   - Each worker processes a subset of vehicles independently

2. **Redis Clustering**:
   - Deploy Redis Cluster for high availability and data partitioning
   - Use Redis Streams for event logging instead of lists

3. **Persistent Storage**:
   - Add PostgreSQL or MongoDB for historical data
   - Implement data archival for completed deliveries

4. **LLM Integration**:
   - Replace rule-based reasoning with OpenAI GPT-4 or local Ollama
   - Use vehicle memory as context for intelligent decision-making

5. **Advanced Routing**:
   - Integrate with real routing APIs (Google Maps, OSRM)
   - Implement machine learning models for traffic prediction

## Configuration

To customize the simulation, edit `config.py`:

```python
NUM_VEHICLES = 5        # Number of vehicles in the fleet
NUM_ORDERS = 50         # Number of orders to deliver
GRID_SIZE = 20          # Grid size in miles (20x20)
DEPOT = (0, 0)          # Depot location
```

For production, use environment variables:

```bash
export REDIS_HOST=redis.production.com
export REDIS_PORT=6379
export NUM_VEHICLES=100
export NUM_ORDERS=1000
```

Then update `config.py` to read from `os.environ`.

## Future Enhancements

1. **Real LLM Integration**: Replace placeholder with actual OpenAI/Ollama calls
2. **Machine Learning**: Predict traffic patterns and optimize routes proactively
3. **Multi-Depot Support**: Handle multiple distribution centers
4. **Customer Integration**: API for real-time order placement and tracking
5. **Analytics Dashboard**: Advanced metrics, KPI tracking, and reporting
6. **Mobile App**: Native iOS/Android app for driver communication

## Performance Metrics

The dashboard displays key performance indicators:

| Metric | Description |
| --- | --- |
| **Total Deliveries** | Number of packages delivered vs. total orders |
| **Active Vehicles** | Count of vehicles currently in use |
| **Distance Saved** | Dynamic calculation of miles avoided due to AI optimization |
| **Cost per Mile** | Dynamic calculation of cost per mile, reflecting AI savings |
| **Avg Delivery Time** | Average time from depot to delivery point |
| **Avg Delivery Miles** | Average distance per delivery |
| **Total Miles** | Cumulative distance traveled by all vehicles |

## Troubleshooting

### Issue: "Connection refused" error
**Solution**: Ensure Redis is running on `localhost:6379`. Check with:
```bash
redis-cli ping
```

### Issue: Streamlit app crashes
**Solution**: Check the console for error messages. Common causes:
- Redis connection lost
- Missing dependencies (install with `pip install -r requirements.txt`)
- Python version incompatibility (use Python 3.8+)

### Issue: Vehicles not moving
**Solution**: Check that the background thread is running. Verify in the console that `move_vehicles()` is being called.

## Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -am 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a pull request

## License

This project is open-source and available under the MIT License.

## Contact & Support

For questions, issues, or suggestions, please open an issue on GitHub or contact the development team.

---

**Built for the Hackathon**: Transform an AI Agent into a scalable business solution with Redis.
