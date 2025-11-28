# main.py - Orchestrator for FlowGrid Logistics AI Agent

import streamlit as st
import random
from simulation import initialize_simulation, start_simulation, safe_redis_hget, safe_redis_hset
from ui import render_ui
from config import GRID_SIZE, NUM_VEHICLES

# --- Application Orchestration ---

# 1. Initialize Traffic Simulation Parameters (using Streamlit session state for persistence)
if 'traffic_step' not in st.session_state:
    # Traffic starts randomly between step 20 and 40
    st.session_state['traffic_step'] = random.randint(20, 40) 
if 'traffic_zone' not in st.session_state:
    # Traffic zone is a random block in the grid
    st.session_state['traffic_zone'] = (random.randint(5, GRID_SIZE - 5), random.randint(5, GRID_SIZE - 5))

# 2. Initialize Simulation State (Orders and Vehicles in Redis)
orders = initialize_simulation()

# 3. Start Background Simulation Thread
# This is safe to call multiple times, as the thread is only started once 
# and runs forever (daemon=True)
start_simulation(st.session_state['traffic_step'], st.session_state['traffic_zone'])

# 4. Render Streamlit UI (This loop runs continuously)

# Compute metrics needed for the UI
total_delivery_time_sum = 0
total_delivery_miles_sum = 0
total_deliveries_computed = 0
total_miles = 0

# Compute metrics from Redis
for v_id in range(NUM_VEHICLES):
    delivered = int(safe_redis_hget(f"vehicle:{v_id}", "delivered", 0))
    total_deliveries_computed += delivered
    for d in range(1, delivered + 1):
        t = float(safe_redis_hget(f"vehicle:{v_id}", f"delivery_time_{d}", 0))
        m = float(safe_redis_hget(f"vehicle:{v_id}", f"delivery_miles_{d}", 0))
        total_delivery_time_sum += t
        total_delivery_miles_sum += m
        total_miles += m

if total_deliveries_computed > 0:
    avg_delivery_time = total_delivery_time_sum / total_deliveries_computed
    avg_delivery_miles = total_delivery_miles_sum / total_deliveries_computed
else:
    avg_delivery_time = 0
    avg_delivery_miles = 0

# Store metrics in Redis for ui.py to retrieve
safe_redis_hset("metrics", mapping={
    "avg_delivery_time": avg_delivery_time,
    "avg_delivery_miles": avg_delivery_miles,
    "total_deliveries_computed": total_deliveries_computed,
    "total_miles": total_miles
})

render_ui(orders, total_miles, total_deliveries_computed)

# --- End of Orchestrator ---
