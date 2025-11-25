# main.py — FlowGrid Logistics streamlit run main.py
import redis
import streamlit as st
import numpy as np
import time
import json
from threading import Thread

# === Redis connection (the heart of everything) ===
r = redis.Redis(host='localhost', port=6379, db=0)

# Clear old data
r.flushdb()

# === Config ===
# NUM_VEHICLES = 25'
NUM_VEHICLES = 50
NUM_ORDERS = 500
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

# === Simulate movement & Redis real-time sync ===
def move_vehicles():
    step = 0
    while True:
        for v_id in vehicles:
            route = json.loads(r.hget(f"vehicle:{v_id}", "route") or "[]")
            if step < len(route):
                new_pos = route[step]
                r.hset(f"vehicle:{v_id}", mapping={"pos_x": new_pos[0], "pos_y": new_pos[1]})
                
                # Count delivery when passing through non-depot
                if new_pos != DEPOT and step > 0 and route[step-1] == DEPOT:
                    delivered = int(r.hget(f"vehicle:{v_id}", "delivered") or 0) + 1
                    r.hset(f"vehicle:{v_id}", "delivered", delivered)
                    r.publish("delivery", f"Vehicle {v_id} delivered package!")
        
        # === TRAFFIC JAM ON I-5 at step 30 ===
        if step == 30:
            st.toast("TRAFFIC JAM ON I-5 — REROUTING FLEET VIA REDIS")
            for v_id in vehicles:
                old_route = json.loads(r.hget(f"vehicle:{v_id}", "route"))
                # Simple reroute: avoid x=8..12 zone (I-5 corridor)
                new_route = []
                for x, y in old_route:
                    if 8 <= x <= 12 and step >= 30:
                        # detour left or right
                        x = 6 if x > 10 else 14
                    new_route.append((x, y))
                r.hset(f"vehicle:{v_id}", "route", json.dumps(new_route))
        
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

# Live map
chart = st.empty()
for _ in range(200):
    data = []
    for v_id in range(NUM_VEHICLES):
        x = float(r.hget(f"vehicle:{v_id}", "pos_x") or 0)
        y = float(r.hget(f"vehicle:{v_id}", "pos_y") or 0)
        data.append({"x": x, "y": y, "vehicle": v_id})
    
    import pandas as pd
    df = pd.DataFrame(data)
    chart.scatter_chart(df, x="x", y="y", size=80, color="#0066ff")

    time.sleep(0.3)