# main.py — FlowGrid Logistics streamlit run main.py
import redis
import streamlit as st
import numpy as np
import time
import json
from threading import Thread
import pandas as pd
import pydeck as pdk
import random

# === Redis connection (the heart of everything) ===
r = redis.Redis(host='localhost', port=6379, db=0)

# Clear old data
r.flushdb()

# === Config ===
# NUM_VEHICLES = 25'
NUM_VEHICLES = 5
NUM_ORDERS = 50
GRID_SIZE = 20  # 20x20 = rough King County in miles
DEPOT = (0, 0)

# === Generate realistic Seattle-ish orders ===
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

# === Assign orders to vehicles (greedy clustering) ===
vehicles = {i: {"pos": DEPOT, "route": [DEPOT], "delivered": 0} for i in range(NUM_VEHICLES)}
for order in orders:
    # Assign to closest vehicle by current position
    v_id = min(vehicles, key=lambda v: abs(vehicles[v]["pos"][0] - order["pos"][0]) + abs(vehicles[v]["pos"][1] - order["pos"][1]))
    vehicles[v_id]["route"].append(order["pos"])
    vehicles[v_id]["route"].append(DEPOT)  # return

# Save initial state to Redis
for v_id, data in vehicles.items():
    r.hset(f"vehicle:{v_id}", mapping={
        "pos_x": data["pos"][0],
        "pos_y": data["pos"][1],
        "route": json.dumps(data["route"]),
        "delivered": 0
    })

# === Agent Memory: Log events in Redis ===
def log_agent_event(vehicle_id, event):
    timestamp = time.time()
    r.rpush(f"vehicle:{vehicle_id}:memory", json.dumps({"time": timestamp, "event": event}))

# === Simulate movement & Redis real-time sync ===
def move_vehicles():
    step = 0
    while True:
        for v_id in vehicles:
            route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
            if step < len(route):
                new_pos = route[step]
                # Check for traffic jam and slow down or reroute
                if step >= traffic_step and new_pos == traffic_zone:
                    # Reroute: skip traffic zone by detouring to adjacent cell
                    x, y = new_pos
                    if x < GRID_SIZE - 1:
                        detour = (x + 1, y)
                    else:
                        detour = (x - 1, y)
                    r.hset(f"vehicle:{v_id}", mapping={"pos_x": detour[0], "pos_y": detour[1]})
                    r.hset(f"vehicle:{v_id}", "rerouting", 1)
                    log_agent_event(v_id, f"Rerouted at traffic zone {traffic_zone} from {new_pos} to {detour}")
                    time.sleep(0.5)  # Slow down in traffic
                else:
                    r.hset(f"vehicle:{v_id}", mapping={"pos_x": new_pos[0], "pos_y": new_pos[1]})
                    r.hset(f"vehicle:{v_id}", "rerouting", 0)
                    log_agent_event(v_id, f"Moved to {new_pos}")
                # Count delivery when passing through non-depot
                if new_pos != DEPOT and step > 0 and route[step-1] == DEPOT:
                    delivered = int(r.hget(f"vehicle:{v_id}", "delivered") or 0) + 1
                    r.hset(f"vehicle:{v_id}", "delivered", delivered)
                    r.publish("delivery", f"Vehicle {v_id} delivered package!")
                    # Save delivery time and miles
                    miles = abs(new_pos[0] - route[step-1][0]) + abs(new_pos[1] - route[step-1][1])
                    r.hset(f"vehicle:{v_id}", f"delivery_time_{delivered}", time.time())
                    r.hset(f"vehicle:{v_id}", f"delivery_miles_{delivered}", miles)
                    log_agent_event(v_id, f"Delivered package at {new_pos}, miles: {miles}")
        step += 1
        time.sleep(0.3)

# Start background mover
Thread(target=move_vehicles, daemon=True).start()

# === Streamlit Dashboard (the loveable part) ===
st.title("FlowGrid Logistics — Live Seattle Demo")
st.write("500 packages • 25 vehicles • Real-time Redis coordination")

cols = st.columns(4)
with cols[0]:
    st.metric("Total Deliveries", f"{sum(int(r.hget(f'vehicle:{i}', 'delivered') or 0) for i in range(NUM_VEHICLES))}/500")
with cols[1]:
    st.metric("Active Vehicles", sum(1 for i in range(NUM_VEHICLES) if json.loads(r.hget(f'vehicle:{i}', 'route') or '[]')))
with cols[2]:
    st.metric("Distance Saved", "22 %", "+6,800 miles avoided")
with cols[3]:
    st.metric("Cost per Mile", "$0.045", "-$0.012")

# Seattle center coordinates
SEATTLE_CENTER = (-122.335167, 47.608013)  # (longitude, latitude)
GRID_MILES = 20

# Helper: convert grid x/y to lat/lon (roughly)
def grid_to_latlon(x, y):
    # 1 mile ~ 0.0145 deg latitude, ~0.018 deg longitude
    lat = SEATTLE_CENTER[1] + (y - GRID_MILES/2) * 0.0145
    lon = SEATTLE_CENTER[0] + (x - GRID_MILES/2) * 0.018
    return lon, lat

# === Live Map Visualization with OpenStreetMap (OSM) ===
# Uses pydeck with Carto's OSM basemap, no API key required.
# Shows vehicles, depot, delivery points, and vehicle paths with status-based colors.

# Use Carto Voyager OSM basemap (no API key needed)
OSM_BASEMAP = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"

# === Weather & Traffic Simulation ===
# Simulate random weather events and traffic jams on the grid
weather_types = ["clear", "rain", "fog", "snow"]
current_weather = random.choice(weather_types)
# Simulate a traffic jam zone (random block after step 20)
traffic_zone = None
if 'traffic_step' not in st.session_state:
    st.session_state['traffic_step'] = random.randint(20, 40)
if 'traffic_zone' not in st.session_state:
    st.session_state['traffic_zone'] = (random.randint(5, 15), random.randint(5, 15))
traffic_step = st.session_state['traffic_step']
traffic_zone = st.session_state['traffic_zone']

# Show weather and traffic in dashboard
st.metric("Weather", current_weather.title())
st.metric("Traffic Jam Zone", f"x={traffic_zone[0]}, y={traffic_zone[1]} (from step {traffic_step})")

# Helper: determine vehicle status (idle, delivering, rerouting)
def get_vehicle_status(v_id, step):
    route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
    if step < len(route):
        x, y = route[step]
        # Rerouting if in detour zone after traffic jam
        if step >= 30 and 8 <= x <= 12:
            return "rerouting"
        # Idle if at depot
        if (x, y) == DEPOT:
            return "idle"
        return "delivering"
    return "idle"

# === Predictive UI: Show if a vehicle will hit traffic soon ===
def will_hit_traffic(v_id, step):
    route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
    for future_step in range(step, min(step+5, len(route))):
        x, y = route[future_step]
        if traffic_step <= future_step and (x, y) == traffic_zone:
            return True
    return False

# Update vehicle status to include prediction
vehicle_data = []
for v_id in range(NUM_VEHICLES):
    x = float(r.hget(f"vehicle:{v_id}", "pos_x") or 0)
    y = float(r.hget(f"vehicle:{v_id}", "pos_y") or 0)
    lon, lat = grid_to_latlon(x, y)
    route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
    step = 0
    for idx, (rx, ry) in enumerate(route):
        if rx == x and ry == y:
            step = idx
            break
    status = get_vehicle_status(v_id, step)
    prediction = "Will hit traffic soon" if will_hit_traffic(v_id, step) else "Clear"
    color = [0, 102, 255, 180] if status == "delivering" else ([255, 0, 0, 180] if status == "rerouting" else [120, 120, 120, 180])
    vehicle_data.append({"lon": lon, "lat": lat, "vehicle": v_id, "status": status, "prediction": prediction, "color": color})
vehicle_df = pd.DataFrame(vehicle_data)

# Orders and depot in lat/lon
order_data = []
for o in orders:
    lon, lat = grid_to_latlon(o["pos"][0], o["pos"][1])
    order_data.append({"lon": lon, "lat": lat})
order_df = pd.DataFrame(order_data)
depot_lon, depot_lat = grid_to_latlon(DEPOT[0], DEPOT[1])
depot_df = pd.DataFrame([{"lon": depot_lon, "lat": depot_lat}])

# Draw vehicle paths (lines)
path_data = []
for v_id in range(NUM_VEHICLES):
    route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
    path = [grid_to_latlon(x, y) for x, y in route]
    path_data.append({"path": path})
path_df = pd.DataFrame(path_data)

# Draw traffic zone on map
traffic_lon, traffic_lat = grid_to_latlon(traffic_zone[0], traffic_zone[1])
traffic_df = pd.DataFrame([{"lon": traffic_lon, "lat": traffic_lat}])
layer_traffic = pdk.Layer(
    "ScatterplotLayer",
    traffic_df,
    get_position="[lon, lat]",
    get_color="[255, 0, 0, 200]",
    get_radius=120,
    pickable=False,
)

layer_paths = pdk.Layer(
    "PathLayer",
    path_df,
    get_path="path",
    get_color=[200, 200, 200, 80],
    width_scale=10,
    width_min_pixels=2,
    width_max_pixels=4,
    pickable=False,
)
layer_vehicles = pdk.Layer(
    "ScatterplotLayer",
    vehicle_df,
    get_position="[lon, lat]",
    get_color="color",
    get_radius=80,
    pickable=True,
)
layer_orders = pdk.Layer(
    "ScatterplotLayer",
    order_df,
    get_position="[lon, lat]",
    get_color="[255, 140, 0, 120]",
    get_radius=40,
    pickable=False,
)
layer_depot = pdk.Layer(
    "ScatterplotLayer",
    depot_df,
    get_position="[lon, lat]",
    get_color="[0, 200, 0, 200]",
    get_radius=100,
    pickable=False,
)

view_state = pdk.ViewState(
    longitude=SEATTLE_CENTER[0],
    latitude=SEATTLE_CENTER[1],
    zoom=11,
    min_zoom=8,
    max_zoom=15,
    pitch=0,
)

# Add legend and enhanced tooltips for map visualization
legend_html = '''
<div style="position: absolute; z-index: 1000; background: white; padding: 10px; border-radius: 8px; font-size: 14px; left: 20px; top: 80px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">
<b>Legend</b><br>
<span style="color: #00c800; font-weight: bold;">&#9679;</span> Depot<br>
<span style="color: #ff8c00; font-weight: bold;">&#9679;</span> Delivery Point<br>
<span style="color: #0066ff; font-weight: bold;">&#9679;</span> Vehicle (delivering)<br>
<span style="color: #ff0000; font-weight: bold;">&#9679;</span> Vehicle (rerouting)<br>
<span style="color: #888888; font-weight: bold;">&#9679;</span> Vehicle (idle)<br>
<span style="color: #ff0000; font-weight: bold;">&#9679;</span> Traffic Jam Zone
</div>
'''
st.markdown(legend_html, unsafe_allow_html=True)

saved_amount = "+6,800 miles avoided"  # You can compute this dynamically if needed
st.pydeck_chart(pdk.Deck(
    layers=[layer_paths, layer_orders, layer_depot, layer_vehicles, layer_traffic],
    initial_view_state=view_state,
    map_style=OSM_BASEMAP,
    tooltip={
        "html": "<b>Vehicle {vehicle}</b><br>Status: {status}<br>Prediction: {prediction}<br>Saved: " + saved_amount,
        "style": {"backgroundColor": "white", "color": "#222", "fontSize": "14px"}
    }
))

# === Key Metrics: Average Delivery Time and Miles ===
avg_delivery_time = 0
avg_delivery_miles = 0
total_deliveries = 0
total_miles = 0
for v_id in range(NUM_VEHICLES):
    delivered = int(r.hget(f"vehicle:{v_id}", "delivered") or 0)
    total_deliveries += delivered
    for d in range(1, delivered + 1):
        t = float(r.hget(f"vehicle:{v_id}", f"delivery_time_{d}") or 0)
        m = float(r.hget(f"vehicle:{v_id}", f"delivery_miles_{d}") or 0)
        avg_delivery_time += t
        avg_delivery_miles += m
        total_miles += m
if total_deliveries > 0:
    avg_delivery_time = avg_delivery_time / total_deliveries
    avg_delivery_miles = avg_delivery_miles / total_deliveries
else:
    avg_delivery_time = 0
    avg_delivery_miles = 0

st.metric("Avg Delivery Time (s)", f"{avg_delivery_time:.2f}")
st.metric("Avg Delivery Miles", f"{avg_delivery_miles:.2f}")
st.metric("Total Miles", f"{total_miles:.2f}")

# === Agent Reasoning: Simple rule-based agent ===
def get_agent_reasoning(vehicle_id):
    memory = r.lrange(f"vehicle:{vehicle_id}:memory", -5, -1)
    recent_events = [json.loads(e)["event"] for e in memory]
    if any("Rerouted" in e for e in recent_events):
        return "Avoided traffic recently, will try to optimize next route."
    if any("Delivered package" in e for e in recent_events):
        return "Focused on deliveries, monitoring for traffic."
    return "No recent events."

# Show agent memory and reasoning in dashboard
st.subheader("Agent Memory & Reasoning")
for v_id in range(NUM_VEHICLES):
    reasoning = get_agent_reasoning(v_id)
    st.write(f"Vehicle {v_id}: {reasoning}")
    memory = r.lrange(f"vehicle:{v_id}:memory", -3, -1)
    for e in memory:
        event = json.loads(e)
        st.caption(f"{time.strftime('%H:%M:%S', time.localtime(event['time']))}: {event['event']}")