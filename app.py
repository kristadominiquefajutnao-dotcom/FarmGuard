import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from database import init_db, add_observation, get_observations, get_crops, update_status, delete_observation, add_sample_data
from prioritization import calculate_urgency, priority_label
from dsa.tree import FarmNode
from dsa.max_heap import MaxHeap
from dsa.linked_list import LinkedList
from dsa.hash_table import HashTable
from dsa.sorting import merge_sort

st.set_page_config(page_title="FarmGuard", page_icon="🌱", layout="wide")
init_db()

st.markdown("""
<style>
    .stApp { background: #f7faf7; }
    [data-testid="stSidebar"] { background: #eaf3e9; }
    .main-title { color: #185b35; font-weight: 800; }
    div[data-testid="stMetric"] { background: white; padding: 14px; border-radius: 12px; border: 1px solid #dce9dd; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🌱 FarmGuard")
    st.caption("Crop Health Monitoring & Inspection Prioritization")
    page = st.radio("Navigation", [
        "Dashboard", "Add Observation", "Farm Records",
        "Crop Health History", "Inspection Prioritization",
        "Inspection Management", "DSA Demonstration", "About"
    ])
    st.divider()
    if st.button("Load sample data", use_container_width=True):
        add_sample_data()
        st.success("Sample records added (if the database was empty).")

def current_data():
    rows = get_observations()
    for row in rows:
        row["urgency_score"] = calculate_urgency(
            row["severity"], row["affected_area"], row["recurrence_count"]
        )
        row["priority"] = priority_label(row["urgency_score"])
    return rows

def show_table(rows):
    if not rows:
        st.info("No records found yet.")
        return
    df = pd.DataFrame(rows)
    preferred = ["observation_id", "crop_id", "crop_type", "crop_name", "location",
                 "observation_date", "symptoms", "severity", "affected_area",
                 "recurrence_count", "urgency_score", "priority", "status"]
    df = df[[c for c in preferred if c in df.columns]]
    st.dataframe(df, use_container_width=True, hide_index=True)

if page == "Dashboard":
    st.title("FarmGuard Dashboard")
    st.write("A simple workspace for recording crop observations and organizing inspection priorities.")
    rows = current_data()
    df = pd.DataFrame(rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Crop records", len(get_crops()))
    c2.metric("Observations", len(rows))
    c3.metric("Urgent priorities", sum(1 for r in rows if r["priority"] in ["Critical", "High"]))
    c4.metric("Pending inspections", sum(1 for r in rows if r["status"] == "Pending Inspection"))
    if rows:
        left, right = st.columns(2)
        with left:
            st.subheader("Observations by severity")
            counts = df["severity"].value_counts().rename_axis("Severity").reset_index(name="Count")
            st.plotly_chart(px.bar(counts, x="Severity", y="Count", color="Severity"), use_container_width=True)
        with right:
            st.subheader("Inspection status")
            counts = df["status"].value_counts().rename_axis("Status").reset_index(name="Count")
            st.plotly_chart(px.pie(counts, names="Status", values="Count", hole=.45), use_container_width=True)
        st.subheader("Highest-priority observations")
        show_table(sorted(rows, key=lambda r: r["urgency_score"], reverse=True)[:5])
    else:
        st.info("Start by adding a crop observation, or use 'Load sample data' in the sidebar to explore the demo.")

elif page == "Add Observation":
    st.title("Add Crop Observation")
    with st.form("observation_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            crop_type = st.selectbox("Crop type", ["Rice", "Mango", "Banana", "Coconut", "Corn", "Other"])
            crop_name = st.text_input("Crop name / variety", placeholder="e.g. NSIC Rc 222 or Carabao Mango")
            location = st.text_input("Farm / field location", placeholder="e.g. Field A, Barangay...")
            section = st.text_input("Field section / tree ID", placeholder="e.g. Plot 2 or Tree 05")
            obs_date = st.date_input("Observation date", value=date.today())
        with col2:
            symptoms = st.text_area("Observed symptoms", placeholder="Describe what you observed")
            severity = st.selectbox("Severity", ["Low", "Moderate", "High", "Critical"])
            affected_area = st.number_input("Estimated affected area (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            notes = st.text_area("Additional notes")
        submitted = st.form_submit_button("Save observation", type="primary", use_container_width=True)
        if submitted:
            if not crop_name.strip() or not location.strip() or not symptoms.strip():
                st.error("Please complete crop name, location, and observed symptoms.")
            else:
                add_observation(crop_type, crop_name.strip(), location.strip(), section.strip(),
                                obs_date.isoformat(), symptoms.strip(), severity,
                                float(affected_area), notes.strip())
                st.success("Observation saved successfully.")

elif page == "Farm Records":
    st.title("Farm Records")
    rows = current_data()
    if rows:
        q = st.text_input("Search by crop, Crop ID, or location")
        crop_types = ["All"] + sorted({r["crop_type"] for r in rows})
        selected_type = st.selectbox("Crop type", crop_types)
        filtered = rows
        if q:
            filtered = [r for r in filtered if q.lower() in " ".join(str(r[k]) for k in ["crop_id","crop_name","location"]).lower()]
        if selected_type != "All":
            filtered = [r for r in filtered if r["crop_type"] == selected_type]
        sort_by = st.selectbox("Sort records by", ["Newest first", "Oldest first", "Highest urgency", "Largest affected area"])
        if sort_by == "Newest first":
            filtered.sort(key=lambda r: r["observation_date"], reverse=True)
        elif sort_by == "Oldest first":
            filtered.sort(key=lambda r: r["observation_date"])
        elif sort_by == "Highest urgency":
            filtered.sort(key=lambda r: r["urgency_score"], reverse=True)
        else:
            filtered.sort(key=lambda r: r["affected_area"], reverse=True)
        show_table(filtered)
    else:
        st.info("No farm records yet. Add an observation first.")

elif page == "Crop Health History":
    st.title("Crop Health History")
    rows = current_data()
    crop_ids = sorted({r["crop_id"] for r in rows})
    if crop_ids:
        chosen = st.selectbox("Select crop record", crop_ids)
        history = [r for r in rows if r["crop_id"] == chosen]
        history.sort(key=lambda r: r["observation_date"])
        st.subheader(history[0]["crop_name"] + " — " + history[0]["location"])
        show_table(history)
        if len(history) > 1:
            chart_df = pd.DataFrame(history)
            st.subheader("Affected area over time")
            st.plotly_chart(px.line(chart_df, x="observation_date", y="affected_area", markers=True,
                                    labels={"observation_date":"Observation date","affected_area":"Affected area (%)"}),
                            use_container_width=True)
    else:
        st.info("No crop history available yet.")

elif page == "Inspection Prioritization":
    st.title("Inspection Prioritization")
    st.write("Higher scores appear first. The score is a decision-support aid, not a plant disease diagnosis.")
    rows = current_data()
    prioritized = sorted(rows, key=lambda r: r["urgency_score"], reverse=True)
    show_table(prioritized)
    with st.expander("How is the urgency score calculated?"):
        st.markdown("""
        - **Severity (50%)**: Low=1, Moderate=2, High=3, Critical=4, normalized to 0–100.
        - **Affected area (30%)**: the recorded percentage, from 0–100.
        - **Recurring symptoms (20%)**: recurrence count is normalized to a maximum of 5 previous matching observations.

        Formula: `0.50 × severity + 0.30 × affected area + 0.20 × recurrence`.

        This is a transparent example scoring model. Farmers should confirm observations with a qualified agricultural technician when needed.
        """)

elif page == "Inspection Management":
    st.title("Inspection Management")
    rows = current_data()
    if rows:
        choices = {f'{r["observation_id"]} — {r["crop_name"]} ({r["severity"]})': r for r in rows}
        label = st.selectbox("Choose observation", list(choices))
        selected = choices[label]
        st.write(f'**Location:** {selected["location"]} | **Current status:** {selected["status"]}')
        new_status = st.radio("Update status", ["Pending Inspection", "Inspected"],
                              index=0 if selected["status"] == "Pending Inspection" else 1)
        if st.button("Update inspection status", type="primary"):
            update_status(selected["observation_id"], new_status)
            st.success("Inspection status updated.")
            st.rerun()
        if st.button("Delete this observation", type="secondary"):
            st.session_state["confirm_delete"] = selected["observation_id"]
        if st.session_state.get("confirm_delete") == selected["observation_id"]:
            st.warning("Are you sure you want to delete this observation?")
            a, b = st.columns(2)
            if a.button("Yes, delete"):
                delete_observation(selected["observation_id"])
                st.session_state.pop("confirm_delete", None)
                st.rerun()
            if b.button("Cancel"):
                st.session_state.pop("confirm_delete", None)
                st.rerun()
        st.subheader("All inspection statuses")
        show_table(rows)
    else:
        st.info("No observations to manage.")

elif page == "DSA Demonstration":
    st.title("DSA Demonstration")
    rows = current_data()
    st.caption("These custom classes demonstrate the required data structures and algorithms.")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Tree ADT", "Max Heap", "Linked List", "Hash Table", "Sorting"])
    with tab1:
        st.subheader("Farm → Crop type → Field / location")
        root = FarmNode("Farm")
        for crop_type in sorted({r["crop_type"] for r in rows}):
            crop_node = FarmNode(crop_type)
            root.add_child(crop_node)
            for loc in sorted({r["location"] for r in rows if r["crop_type"] == crop_type}):
                crop_node.add_child(FarmNode(loc))
        st.code("\n".join(root.traverse()), language="text")
    with tab2:
        heap = MaxHeap()
        for r in rows:
            heap.insert((r["urgency_score"], r["observation_id"], r["crop_name"]))
        st.write("Highest urgency item:")
        st.write(heap.peek() if not heap.is_empty() else "No observations yet.")
        st.write("Heap array (score, observation ID, crop name):")
        st.code(str(heap.items))
    with tab3:
        crop_ids = sorted({r["crop_id"] for r in rows})
        if crop_ids:
            chosen = st.selectbox("Crop ID for linked-list history", crop_ids, key="ll_crop")
            ll = LinkedList()
            for r in sorted([x for x in rows if x["crop_id"] == chosen], key=lambda x: x["observation_date"]):
                ll.append(f'{r["observation_date"]}: {r["symptoms"]} ({r["severity"]})')
            st.code("\n".join(ll.traverse()) or "No history")
        else:
            st.info("Add observations to demonstrate the linked list.")
    with tab4:
        ht = HashTable()
        for r in rows:
            ht.insert(r["observation_id"], r["crop_name"])
        key = st.text_input("Enter an Observation ID to look up", key="hash_key")
        if st.button("Search hash table"):
            result = ht.search(key)
            st.write(result if result is not None else "No matching observation ID.")
        st.caption(f"Hash table currently contains {len(ht)} observation records.")
    with tab5:
        sorted_rows = merge_sort(rows, key=lambda r: r["urgency_score"], reverse=True)
        st.write("Merge Sort result (highest urgency first):")
        show_table(sorted_rows)

else:
    st.title("About FarmGuard")
    st.markdown("""
    **FarmGuard** is a Python-based crop observation and inspection prioritization application.

    It helps farmers record crop conditions, review observation history, and organize which
    recorded areas may need inspection first.

    **Important limitation:** FarmGuard does not diagnose crop diseases or recommend pesticide
    treatments. It organizes user-entered observations and calculates a transparent inspection
    priority score.

    **Data Structures and Algorithms:** Tree ADT, Max Heap, Linked List, Hash Table, and Merge Sort.
    """)
