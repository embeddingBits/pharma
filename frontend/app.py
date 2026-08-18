import os
import tempfile
import time

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

BACKEND_URL = os.environ.get("PHARMA_BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="PharmaGen CDSS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main-header { font-size:2.2rem; font-weight:700; color:#F8FAFC; }
    .sub-text { font-size:1rem; color:#94A3B8; margin-bottom:20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">PharmaGen Precision Oncology CDSS</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deterministic Knowledge-Graph Clinical Decision Support Engine</div>', unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("Upload Genomics VCF Stream", type=["vcf", "txt"])

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    if not file_bytes:
        st.error("Uploaded file is empty.")
        st.stop()

    with st.spinner("Executing Deterministic Evidence Lookup..."):
        start_time = time.perf_counter()
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/v1/analyze",
                files={"file": (uploaded_file.name, file_bytes)},
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            st.error(
                f"Could not reach the backend at {BACKEND_URL}. "
                "Make sure it is running (./run.sh) before uploading a file."
            )
            st.stop()
        except requests.exceptions.Timeout:
            st.error("The backend timed out. Try again with a smaller file.")
            st.stop()
        latency_ms = (time.perf_counter() - start_time) * 1000

    if response.status_code == 200:
        data = response.json()

        flat_rows = []
        for item in data["annotated_results"]:
            v = item["variant_info"]
            for m in item["clinical_matches"]:
                flat_rows.append({
                    "Gene": v["gene"],
                    "Mutation": v["mutation"],
                    "Chromosome": v["chrom"],
                    "Disease": m["disease"],
                    "Targeted Drug": m["therapy"],
                    "Evidence Level": m["evidence_tier"],
                    "Source": m["source"]
                })

        df = pd.DataFrame(flat_rows)

        # Sidebar Filter Controls
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filter Clinical Matrix")
        all_levels = df["Evidence Level"].unique().tolist() if not df.empty else []
        default_levels = [lvl for lvl in all_levels if "Level A" in lvl or "Level B" in lvl]

        selected_levels = st.sidebar.multiselect(
            "Evidence Tiers",
            options=all_levels,
            default=default_levels if default_levels else all_levels
        )

        filtered_df = df[df["Evidence Level"].isin(selected_levels)] if selected_levels else df

        # Metrics display
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Variants", data["variants_count"])
        c2.metric("Filtered Biomarkers", len(filtered_df))
        c3.metric("High-Confidence (Level A/B)", len(df[df["Evidence Level"].str.contains("Level A|Level B")]) if not df.empty else 0)
        c4.metric("Engine Latency", f"{latency_ms:.0f} ms")

        st.markdown("---")
        t1, t2 = st.tabs(["Actionable Treatment Matrix", "Interactive Knowledge Graph"])

        with t1:
            if df.empty:
                st.info("No clinical evidence matched the uploaded variants.")
            else:
                st.dataframe(filtered_df, use_container_width=True, height=420)

        with t2:
            st.caption("Node Hierarchy: Gene (Red) -> Mutation (Yellow) -> Disease (Blue) -> Drug (Green)")

            net = Network(height="580px", width="100%", directed=True, bgcolor="#0e1117", font_color="white")

            # Physics settings to push nodes apart and prevent overlapping text
            net.set_options("""
            var options = {
              "nodes": {
                "font": { "size": 13, "face": "sans-serif", "color": "#ffffff" },
                "borderWidth": 2
              },
              "edges": {
                "font": { "size": 11, "align": "top", "color": "#94a3b8" },
                "smooth": { "type": "continuous", "roundness": 0.2 }
              },
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -12000,
                  "centralGravity": 0.2,
                  "springLength": 180,
                  "springConstant": 0.04,
                  "damping": 0.09
                }
              }
            }
            """)

            COLOR_MAP = {"Gene": "#FF4B4B", "Mutation": "#FFAA00", "Disease": "#00C0F2", "Drug": "#00D47E"}

            # Render matches per variant inside the knowledge graph
            for record in data["annotated_results"]:
                v = record["variant_info"]
                gene_id = f"Gene:{v['gene']}"
                mut_id = f"Mut:{v['gene']}_{v['mutation']}"

                net.add_node(gene_id, label=f"Gene: {v['gene']}", color=COLOR_MAP["Gene"], shape="ellipse")
                net.add_node(mut_id, label=f"Mut: {v['mutation']}", color=COLOR_MAP["Mutation"], shape="diamond")
                net.add_edge(gene_id, mut_id, label="HAS_MUTATION", color="#475569")

                # Filter for top matches based on sidebar selections
                matches = [m for m in record["clinical_matches"] if m["disease"] != "No Direct Match"]
                selected_matches = [m for m in matches if m["evidence_tier"] in selected_levels][:4]

                for match in selected_matches:
                    disease_id = f"Disease:{match['disease']}"
                    drug_id = f"Drug:{match['therapy']}"

                    net.add_node(disease_id, label=match['disease'], color=COLOR_MAP["Disease"], shape="box")
                    net.add_node(drug_id, label=match['therapy'][:25], color=COLOR_MAP["Drug"], shape="star", title=match['therapy'])

                    net.add_edge(mut_id, disease_id, label="INDICATES", color="#334155")
                    net.add_edge(mut_id, drug_id, label=match['evidence_tier'], color="#00D47E")

            graph_html = net.generate_html(notebook=False)
            components.html(graph_html, height=600)

    else:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        st.error(f"API Error {response.status_code}: {detail}")