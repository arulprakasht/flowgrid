import streamlit as st
import pandas as pd
import pydeck as pdk
import json
import time
import random
from config import *
from simulation import r, safe_redis_hget, llm_agent_reasoning, get_agent_reasoning

def grid_to_latlon(x, y):
    """Converts grid coordinates to approximate latitude and longitude for the Seattle area."""
    lat = SEATTLE_CENTER[1] + (y - GRID_MILES/2) * 0.0145
    lon = SEATTLE_CENTER[0] + (x - GRID_MILES/2) * 0.018
    return lon, lat

def get_vehicle_status(v_id, step, route, traffic_step, traffic_zone):
    if step < len(route):
        x, y = route[step]
        rerouting_status = safe_redis_hget(f"vehicle:{v_id}", "rerouting", 0)
        if int(rerouting_status) == 1:
            return "rerouting"
        if (x, y) == DEPOT:
            return "idle"
        return "delivering"
    return "idle"

def will_hit_traffic(v_id, step, route, traffic_step, traffic_zone):
    for future_step in range(step, min(step+5, len(route))):
        x, y = route[future_step]
        if traffic_step <= future_step and (x, y) == traffic_zone:
            return True
    return False

def render_ui(orders, total_miles, total_deliveries_computed):
    traffic_step = st.session_state['traffic_step']
    traffic_zone = st.session_state['traffic_zone']
    st.title("FlowGrid Logistics — Live AI Agent Demo")
    st.write(f"{NUM_ORDERS} packages • {NUM_VEHICLES} vehicles • Real-time Redis coordination")
    active_vehicles = sum(1 for i in range(NUM_VEHICLES) if json.loads(safe_redis_hget(f'vehicle:{i}', 'route', '[]')))
    cols = st.columns(4)
    with cols[0]:
        st.metric("Total Deliveries", f"{total_deliveries_computed}/{NUM_ORDERS}")
    with cols[1]:
        st.metric("Active Vehicles", active_vehicles)
    with cols[2]:
        total_direct_distance = sum(abs(o["pos"][0] - DEPOT[0]) + abs(o["pos"][1] - DEPOT[1]) for o in orders)
        total_optimized_distance = total_miles
        if total_optimized_distance > 0:
            baseline_distance = total_direct_distance * 1.5
            distance_saved_miles = baseline_distance - total_optimized_distance
            distance_saved_percent = (distance_saved_miles / baseline_distance) * 100 if baseline_distance > 0 else 0
        else:
            distance_saved_miles = 0
            distance_saved_percent = 0
        st.metric("Distance Saved", f"{distance_saved_percent:.1f} %", f"{distance_saved_miles:.0f} miles avoided")
    with cols[3]:
        BASE_COST_PER_MILE = 0.06
        if total_deliveries_computed > 0:
            simulated_cost_per_mile = BASE_COST_PER_MILE * (1 - (distance_saved_percent / 200))
            cost_change = BASE_COST_PER_MILE - simulated_cost_per_mile
        else:
            simulated_cost_per_mile = BASE_COST_PER_MILE
            cost_change = 0
        st.metric("Cost per Mile", f"${simulated_cost_per_mile:.3f}", f"${cost_change:.3f} change")
    weather_types = ["clear", "rain", "fog", "snow"]
    current_weather = random.choice(weather_types)
    st.subheader("Simulation Parameters")
    if st.button("Reset Simulation"):
        st.session_state['traffic_step'] = random.randint(20, 40)
        st.session_state['traffic_zone'] = (random.randint(5, GRID_SIZE - 5), random.randint(5, GRID_SIZE - 5))
        st.rerun()
    cols_sim = st.columns(2)
    with cols_sim[0]:
        st.metric("Weather", current_weather.title())
    with cols_sim[1]:
        st.metric("Traffic Jam Zone", f"x={traffic_zone[0]}, y={traffic_zone[1]} (from step {traffic_step})")
    vehicle_data = []
    for v_id in range(NUM_VEHICLES):
        x = float(safe_redis_hget(f"vehicle:{v_id}", "pos_x", 0))
        y = float(safe_redis_hget(f"vehicle:{v_id}", "pos_y", 0))
        lon, lat = grid_to_latlon(x, y)
        route_json = safe_redis_hget(f"vehicle:{v_id}", "route", '[]')
        route = json.loads(route_json)
        step = 0
        for idx, (rx, ry) in enumerate(route):
            if rx == x and ry == y:
                step = idx
                break
        status = get_vehicle_status(v_id, step, route, traffic_step, traffic_zone)
        prediction = "Will hit traffic soon" if will_hit_traffic(v_id, step, route, traffic_step, traffic_zone) else "Clear"
        if status == "delivering":
            color = [0, 102, 255, 180]
        elif status == "rerouting":
            color = [255, 0, 0, 180]
        else:
            color = [120, 120, 120, 180]
        vehicle_data.append({"lon": lon, "lat": lat, "vehicle": v_id, "status": status, "prediction": prediction, "color": color})
    vehicle_df = pd.DataFrame(vehicle_data)
    order_data = []
    for o in orders:
        lon, lat = grid_to_latlon(o["pos"][0], o["pos"][1])
        order_data.append({"lon": lon, "lat": lat})
    order_df = pd.DataFrame(order_data)
    depot_lon, depot_lat = grid_to_latlon(DEPOT[0], DEPOT[1])
    depot_df = pd.DataFrame([{"lon": depot_lon, "lat": depot_lat}])
    path_data = []
    for v_id in range(NUM_VEHICLES):
        route_json = safe_redis_hget(f"vehicle:{v_id}", "route", '[]')
        route = json.loads(route_json)
        path = [grid_to_latlon(x, y) for x, y in route]
        path_data.append({"path": path})
    path_df = pd.DataFrame(path_data)
    traffic_lon, traffic_lat = grid_to_latlon(traffic_zone[0], traffic_zone[1])
    traffic_df = pd.DataFrame([{"lon": traffic_lon, "lat": traffic_lat}])
    icon_data = {
        "url": TRUCK_ICON_URL,
        "width": 64,
        "height": 64,
        "anchorY": 64
    }
    vehicle_icon_df = pd.DataFrame([
        {"lon": v["lon"], "lat": v["lat"], "vehicle": v["vehicle"], "status": v["status"], "prediction": v["prediction"], "icon_data": icon_data} for v in vehicle_data
    ])
    layer_vehicle_icons = pdk.Layer(
        "IconLayer",
        vehicle_icon_df,
        get_icon="icon_data",
        get_position='[lon, lat]',
        size_scale=20,
        pickable=True,
        get_color=[255,255,255],
    )
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
    st.pydeck_chart(pdk.Deck(
        layers=[layer_paths, layer_orders, layer_depot, layer_vehicle_icons, layer_traffic],
        initial_view_state=view_state,
        map_style=OSM_BASEMAP,
        tooltip={
            "html": "<b>🚚 Vehicle {vehicle}</b><br>Status: {status}<br>Prediction: {prediction}",
            "style": {"backgroundColor": "white", "color": "#222", "fontSize": "15px"}
        }
    ))
    st.subheader("Performance Metrics")
    avg_delivery_time = float(safe_redis_hget("metrics", "avg_delivery_time", 0))
    avg_delivery_miles = float(safe_redis_hget("metrics", "avg_delivery_miles", 0))
    total_miles = float(safe_redis_hget("metrics", "total_miles", 0))
    total_deliveries_computed = int(safe_redis_hget("metrics", "total_deliveries_computed", 0))
    cols_metrics = st.columns(3)
    with cols_metrics[0]:
        st.metric("Avg Delivery Time (s)", f"{avg_delivery_time:.2f}")
    with cols_metrics[1]:
        st.metric("Avg Delivery Miles", f"{avg_delivery_miles:.2f}")
    with cols_metrics[2]:
        st.metric("Total Miles", f"{total_miles:.2f}")
    st.sidebar.header("Agentic AI Control & Chat")
    avg_delivery_time = float(safe_redis_hget("metrics", "avg_delivery_time", 0))
    user_message = st.sidebar.text_input("Ask the AI agent something:", "How are deliveries going?")
    if st.sidebar.button("Send to Agent"):
        if "deliveries" in user_message.lower():
            status = 'on track' if avg_delivery_time < 60 else 'delayed'
            response = f"Agent: Based on real-time metrics, deliveries are **{status}**. Average delivery time is {avg_delivery_time:.2f} seconds. Traffic zone at {traffic_zone} is being actively managed."
        elif "traffic" in user_message.lower():
            response = f"Agent: Traffic is currently simulated at zone {traffic_zone}. Our agents are successfully rerouting, minimizing impact. We project a **{distance_saved_percent:.1f}%** distance saving."
        else:
            response = "Agent: I am an AI Logistics Agent. I can answer questions about deliveries, traffic, and vehicle status."
        st.sidebar.markdown(f"**AI Agent Response:** {response}")
    st.sidebar.subheader("AI Agent Thoughts (Real-time)")
    for v_id in range(NUM_VEHICLES):
        thought = llm_agent_reasoning(v_id, None)
        st.sidebar.markdown(f"<div style='background:#f0f8ff;padding:8px;border-radius:6px;margin-bottom:4px;'><b>🚚 Vehicle {v_id}:</b> <i>{thought}</i></div>", unsafe_allow_html=True)
    st.subheader("Historical Analytics & Reporting")
    history = []
    for v_id in range(NUM_VEHICLES):
        deliveries = int(safe_redis_hget(f"vehicle:{v_id}", "delivered", 0))
        for d in range(1, deliveries + 1):
            t = float(safe_redis_hget(f"vehicle:{v_id}", f"delivery_time_{d}", 0))
            m = float(safe_redis_hget(f"vehicle:{v_id}", f"delivery_miles_{d}", 0))
            history.append({"vehicle": v_id, "delivery": d, "time": t, "miles": m})
    history_df = pd.DataFrame(history)
    if not history_df.empty:
        st.dataframe(history_df)
        st.line_chart(history_df.groupby("vehicle")["miles"].sum())
    st.subheader("Agent Memory Log (Last 3 Events)")
    for v_id in range(NUM_VEHICLES):
        st.markdown(f"**🚚 Vehicle {v_id} Reasoning:** <span style='color:#0066ff'>{get_agent_reasoning(v_id)}</span>", unsafe_allow_html=True)
        memory = r.lrange(f"vehicle:{v_id}:memory", -3, -1)
        for e in memory:
            event = json.loads(e.decode('utf-8'))
            st.caption(f"{time.strftime('%H:%M:%S', time.localtime(event['time']))}: {event['event']}")
