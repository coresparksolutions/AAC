import os
from pathlib import Path

import pandas as pd
import streamlit as st

from check_dr_parallel import process_targets

st.set_page_config(
    page_title="AAC — Ahrefs Authority Checker",
    page_icon="🔍",
    layout="wide",
)


def parse_domains(raw_text: str):
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def get_uploaded_domains(uploaded_file):
    if uploaded_file is None:
        return []
    try:
        text = uploaded_file.read().decode("utf-8")
    except Exception:
        text = uploaded_file.read().decode("latin-1")
    return parse_domains(text)


with st.sidebar:
    st.image(
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=900&q=80",
        use_column_width=True,
    )
    st.title("AAC")
    st.caption("Ahrefs Authority Checker")

    st.markdown("### Configuration")
    api_keys_input = st.text_area(
        "Ahrefs API keys (comma separated)",
        value=os.environ.get("AHREFS_API_KEYS", ""),
        height=120,
        help="Add one or more keys to spread requests across shards.",
    )
    api_keys = [k.strip() for k in api_keys_input.split(",") if k.strip()]

    shard_index = st.number_input("Shard index", min_value=0, max_value=20, value=0, step=1)
    shard_count = st.number_input("Shard count", min_value=1, max_value=20, value=1, step=1)
    rate_limit_delay = st.number_input("Rate limit delay (seconds)", min_value=0.0, max_value=10.0, value=1.1, step=0.1)
    output_dir = st.text_input("Output folder", value="results")

    st.markdown("---")
    st.caption("This dashboard keeps the existing CLI script intact while adding a cleaner workflow for bulk checks.")


st.title("Ahrefs Authority Checker")
st.subheader("Bulk domain authority analysis with a professional dashboard")

intro_col, stat_a, stat_b, stat_c = st.columns([2, 1, 1, 1])
with intro_col:
    st.write(
        "Run large domain checks, review Authority metrics, and export clean CSV results without leaving the browser."
    )
with stat_a:
    st.metric("Targets", "0")
with stat_b:
    st.metric("DR avg", "—")
with stat_c:
    st.metric("Success", "0%")

st.markdown("---")

input_col, upload_col = st.columns([2, 1])
with input_col:
    domain_input = st.text_area(
        "Domain list",
        placeholder="example.com\nmoz.com\nsemrush.com\n",
        height=220,
    )
with upload_col:
    uploaded_file = st.file_uploader("Upload a .txt file", type=["txt"])
    if uploaded_file is not None:
        st.success(f"Loaded file: {uploaded_file.name}")

run_button = st.button("Run domain checks", use_container_width=True, type="primary")

if run_button:
    domain_list = parse_domains(domain_input)
    if uploaded_file is not None:
        domain_list = get_uploaded_domains(uploaded_file)

    if not domain_list:
        st.error("Please provide at least one domain or upload a list file.")
        st.stop()

    if not api_keys:
        st.error("Add at least one Ahrefs API key before starting the check.")
        st.stop()

    api_key = api_keys[shard_index % len(api_keys)]
    os.environ["AHREFS_API_KEYS"] = ",".join(api_keys)
    os.environ["SHARD_INDEX"] = str(shard_index)
    os.environ["SHARD_COUNT"] = str(shard_count)
    os.environ["AAC_RATE_LIMIT_DELAY"] = str(rate_limit_delay)
    os.environ["AAC_OUTPUT_DIR"] = output_dir

    with st.spinner("Processing domain list..."):
        results = process_targets(
            targets=domain_list,
            api_key=api_key,
            shard_index=shard_index,
            shard_count=shard_count,
            output_dir=output_dir,
            rate_limit_delay=rate_limit_delay,
        )

    if not results:
        st.warning("No new targets were processed. Results are already complete for this shard.")
        st.stop()

    df = pd.DataFrame(results, columns=["target", "domain_rating", "error"])
    df["domain_rating"] = pd.to_numeric(df["domain_rating"], errors="coerce")
    df["status"] = df["error"].apply(lambda x: "error" if x else "ok")

    st.markdown("### Results")
    st.dataframe(df, use_container_width=True)

    average_dr = round(df["domain_rating"].mean(), 2) if df["domain_rating"].notna().any() else 0
    success_rate = round((df["status"] == "ok").mean() * 100, 1) if not df.empty else 0

    summary_col_1, summary_col_2, summary_col_3 = st.columns(3)
    summary_col_1.metric("Processed", len(df))
    summary_col_2.metric("Average DR", average_dr)
    summary_col_3.metric("Success", f"{success_rate}%")

    csv_buffer = df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        data=csv_buffer,
        file_name="aac_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    output_file_path = Path(output_dir) / f"shard_{shard_index}.csv"
    if output_file_path.exists():
        st.caption(f"Saved to: {output_file_path}")

st.markdown("---")

st.caption("AAC is built for SEO professionals, outreach teams, and domain researchers who want fast, actionable metrics.")
