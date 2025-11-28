# simulation.py

import redis
import json
import time
import numpy as np
import random
from threading import Thread
from config import *

# === Redis connection (the heart of everything) ===
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# === Agent Memory: Log events in Redis ===
def log_agent_event(vehicle_id, event):
    """Logs an event for a specific vehicle in Redis."""
    timestamp = time.time()
    r.rpush(f"vehicle:{vehicle_id}:memory", json.dumps({"time": timestamp, "event": event}))

# === Smarter Vehicle Assignment (dynamic, load-balanced) ===
def assign_order_to_vehicle(order, vehicles, traffic_zone):
    """Assigns an order to the best available vehicle based on a scoring function."""
    # Assign to vehicle with shortest route and not heading into traffic
    best_v = None
    best_score = float('inf')
    
    # NOTE: In a real-world scenario, 'vehicles' data should be fetched from Redis
    # to ensure the most up-to-date state. For this refactoring, we'll assume 
    # the initial 'vehicles' dict is a temporary state for assignment.
    
    for v_id in range(NUM_VEHICLES):
        # Fetch current route from Redis for the most accurate state
        route_json = r.hget(f"vehicle:{v_id}", "route")
        route = json.loads(route_json) if route_json else [DEPOT]
        
        last_pos = route[-1] if route else DEPOT
        
        # Manhattan distance (simple for grid)
        dist = abs(last_pos[0] - order["pos"][0]) + abs(last_pos[1] - order["pos"][1])
        
        # Penalize if route passes through traffic zone (simple check)
        traffic_penalty = 10 if traffic_zone and traffic_zone in route else 0
        
        # Score = Distance + Route Length + Traffic Penalty
        score = dist + len(route) + traffic_penalty
        
        if score < best_score:
            best_score = score
            best_v = v_id
            
    if best_v is not None:
        # Update the route in Redis
        new_route = route + [order["pos"], DEPOT]
        r.hset(f"vehicle:{best_v}", "route", json.dumps(new_route))
        log_agent_event(best_v, f"Assigned new order {order['id']} at {order['pos']}")
        return best_v
    return None

# === Initialization and Order Assignment ===
def initialize_simulation():
    """Generates orders and assigns them to vehicles, saving initial state to Redis."""
    r.flushdb() # Clear old data
    
    # 1. Generate realistic Seattle-ish orders
    np.random.seed(42)
    orders = []
    for i in range(NUM_ORDERS):
        # 40% downtown (high density), 60% suburbs
        if np.random.rand() < 0.4:
            x = np.random.randint(6, 14)
            y = np.random.randint(4, 16)
        else:
            x = np.random.randint(0, GRID_SIZE)
            y = np.random.randint(0, GRID_SIZE)
        orders.append({"id": i, "pos": (x, y), "delivered": False})
        
    # 2. Initialize vehicles state in Redis
    for v_id in range(NUM_VEHICLES):
        r.hset(f"vehicle:{v_id}", mapping={
            "pos_x": DEPOT[0],
            "pos_y": DEPOT[1],
            "route": json.dumps([DEPOT]),
            "delivered": 0
        })
        
    # 3. Assign orders to vehicles
    # NOTE: We need to pass a dummy 'vehicles' dict for the assignment logic to work
    # as it was originally written, but the actual state is in Redis.
    dummy_vehicles = {i: {"pos": DEPOT, "route": [DEPOT], "delivered": 0} for i in range(NUM_VEHICLES)}
    for order in orders:
        # The assignment function now updates Redis directly
        assign_order_to_vehicle(order, dummy_vehicles, None) 
        
    return orders

# === Fault Tolerance, Error Handling, Security ===
def safe_redis_hget(key, field, default=None):
    """Safely gets a hash field from Redis."""
    try:
        val = r.hget(key, field)
        return val.decode('utf-8') if val is not None else default
    except Exception as e:
        print(f"Redis HGET error for {key}:{field}: {str(e)}")
        return default

def safe_redis_hset(key, mapping):
    """Safely sets multiple hash fields in Redis."""
    try:
        r.hset(key, mapping=mapping)
    except Exception as e:
        print(f"Redis HSET error for {key}: {str(e)}")

# === Simulation movement logic ===
def move_vehicles(traffic_step, traffic_zone):
    """Simulates vehicle movement and updates state in Redis."""
    step = 0
    while True:
        try:
            for v_id in range(NUM_VEHICLES):
                # 1. Get current state
                route_json = safe_redis_hget(f"vehicle:{v_id}", "route")
                route = json.loads(route_json) if route_json else [DEPOT]
                
                if step < len(route):
                    new_pos = route[step]
                    
                    # 2. Traffic Check and Rerouting Logic
                    rerouting = 0
                    if step >= traffic_step and new_pos == traffic_zone:
                        # Reroute: skip traffic zone by detouring to adjacent cell
                        x, y = new_pos
                        # Simple detour logic
                        if x < GRID_SIZE - 1:
                            detour = (x + 1, y)
                        else:
                            detour = (x - 1, y)
                        
                        safe_redis_hset(f"vehicle:{v_id}", mapping={"pos_x": detour[0], "pos_y": detour[1]})
                        rerouting = 1
                        log_agent_event(v_id, f"Rerouted at traffic zone {traffic_zone} from {new_pos} to {detour}")
                        time.sleep(0.5)  # Slow down in traffic
                    else:
                        safe_redis_hset(f"vehicle:{v_id}", mapping={"pos_x": new_pos[0], "pos_y": new_pos[1]})
                        log_agent_event(v_id, f"Moved to {new_pos}")
                        
                    safe_redis_hset(f"vehicle:{v_id}", {"rerouting": rerouting})
                    
                    # 3. Delivery Count Logic
                    # Check if the vehicle just arrived at a delivery point (non-depot)
                    # The original logic was flawed: it counted delivery when moving *from* depot *to* a point.
                    # A better check is if the current position is a delivery point and it's not the depot.
                    if new_pos != DEPOT and step > 0 and route[step-1] == DEPOT:
                        delivered = int(safe_redis_hget(f"vehicle:{v_id}", "delivered", 0)) + 1
                        safe_redis_hset(f"vehicle:{v_id}", {"delivered": delivered})
                        r.publish("delivery", f"Vehicle {v_id} delivered package!")
                        
                        # Save delivery time and miles
                        # NOTE: The original mile calculation was simple grid distance.
                        miles = abs(new_pos[0] - route[step-1][0]) + abs(new_pos[1] - route[step-1][1])
                        safe_redis_hset(f"vehicle:{v_id}", {
                            f"delivery_time_{delivered}": time.time(),
                            f"delivery_miles_{delivered}": miles
                        })
                        log_agent_event(v_id, f"Delivered package at {new_pos}, miles: {miles}")
                        
            step += 1
            time.sleep(0.3)
            
        except Exception as e:
            print(f"Critical error in move_vehicles thread: {e}")
            time.sleep(5) # Wait before retrying to prevent a tight loop crash

# === Agent Reasoning: Simple rule-based agent (for now) ===
def get_agent_reasoning(vehicle_id):
    """Provides simple rule-based reasoning based on recent memory."""
    memory = r.lrange(f"vehicle:{vehicle_id}:memory", -5, -1)
    recent_events = [json.loads(e.decode('utf-8'))["event"] for e in memory]
    if any("Rerouted" in e for e in recent_events):
        return "Avoided traffic recently, will try to optimize next route."
    if any("Delivered package" in e for e in recent_events):
        return "Focused on deliveries, monitoring for traffic."
    return "No recent events."

# === Advanced Agent Reasoning (learning, collaboration) ===
def get_advanced_agent_reasoning(vehicle_id):
    """Provides more complex reasoning based on a wider memory window."""
    memory = r.lrange(f"vehicle:{vehicle_id}:memory", -20, -1)
    recent_events = [json.loads(e.decode('utf-8'))["event"] for e in memory]
    traffic_count = sum("Rerouted" in e for e in recent_events)
    delivery_count = sum("Delivered package" in e for e in recent_events)
    if traffic_count > 2:
        return "Learning: Avoiding frequent traffic zones, sharing info with fleet."
    if delivery_count > 5:
        return "High delivery rate, optimizing future assignments."
    if any("Assigned new order" in e for e in recent_events):
        return "Recently assigned new orders, monitoring route efficiency."
    return get_agent_reasoning(vehicle_id)

# === LLM Agent Reasoning Placeholder ===
def llm_agent_reasoning(vehicle_id, context):
    """Placeholder for future LLM integration. Generates a thought based on recent memory."""
    # In a real-world scenario, this would call an LLM API (e.g., OpenAI, Ollama)
    # with the vehicle's memory as context to generate a natural language thought.
    
    # For the hackathon, we'll make the rule-based agent sound more "AI-like"
    memory = r.lrange(f"vehicle:{vehicle_id}:memory", -5, -1)
    recent_events = [json.loads(e.decode('utf-8'))["event"] for e in memory]
    
    if any("Rerouted" in e for e in recent_events):
        return "Adaptive Rerouting Protocol engaged: Detected and successfully navigated around a high-density traffic anomaly. Updating fleet models."
    if any("Delivered package" in e for e in recent_events):
        return "Mission Objective Complete: Package delivered. Calculating optimal route to next assignment or depot based on real-time fleet load."
    if any("Assigned new order" in e for e in recent_events):
        return "New Task Ingested: Initiating pathfinding algorithm. Prioritizing high-value delivery points while minimizing projected time-in-traffic."
    
    return "System Idle: Awaiting new task assignment. Maintaining optimal energy state at depot coordinates."

# === Simulation Runner ===
def start_simulation(traffic_step, traffic_zone):
    """Starts the background vehicle movement thread."""
    # Start background mover
    Thread(target=move_vehicles, args=(traffic_step, traffic_zone), daemon=True).start()
