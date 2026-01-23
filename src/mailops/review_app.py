from __future__ import annotations

import os
import base64
from io import BytesIO
from pathlib import Path
from typing import List, Set

import streamlit as st
import qrcode

from pypdf import PdfReader, PdfWriter

from mailops.jobs import latest_job_dir, read_json, write_json
from mailops.pdf.exclude import exclude_pages_by_index

def _lan_hint_url(port: int = 8501) -> str:
    # Best-effort: user will replace with their LAN IP if needed
    return f"http://<LAN-IP>:{port}"

def _thumb_data_uri(path) -> str:
    b = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode("ascii")

def _qr_png_bytes(data: str) -> bytes:
    img = qrcode.make(data)  # PIL image
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def _clear_toggle_query_param() -> None:
    try:
        # Streamlit >= 1.30
        if "toggle" in st.query_params:
            del st.query_params["toggle"]
    except Exception:
        # Older Streamlit
        st.experimental_set_query_params()

def _get_toggle_index_from_query() -> int | None:
    try:
        v = st.query_params.get("toggle")
        if v is None:
            return None
        # sometimes it's already a string, sometimes list-like
        if isinstance(v, list):
            v = v[0] if v else None
        return int(v) if v is not None else None
    except Exception:
        qp = st.experimental_get_query_params()
        v = qp.get("toggle", [None])[0]
        return int(v) if v is not None else None

def main() -> None:
    st.set_page_config(page_title="MailOps Review", layout="wide")
    st.title("MailOps Review & Approve Printing")

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        div[data-testid="stVerticalBlock"] { gap: 0.25rem; }
        div[data-testid="stCaptionContainer"] { margin-top: -0.25rem; margin-bottom: -0.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Simple shared-secret gate (LAN only, but still protect it)
    required_pin = os.getenv("MAILOPS_REVIEW_PIN", "")

    if "auth_ok" not in st.session_state:
        st.session_state["auth_ok"] = False

    if required_pin and not st.session_state["auth_ok"]:
        with st.form("pin_form", clear_on_submit=False):
            pin = st.text_input("Enter PIN", type="password")
            submitted = st.form_submit_button("Unlock")

        if submitted:
            if pin == required_pin:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Invalid PIN.")

        st.stop()

    job_dir = latest_job_dir()
    if job_dir is None:
        st.error("No jobs found under output/jobs/. Create a job first.")
        st.stop()

    st.caption(f"Job: {job_dir.name}")

    review_path = job_dir / "review.json"
    imposed_path = job_dir / "imposed.pdf"
    thumbs_dir = job_dir / "thumbs"

    if not review_path.exists() or not imposed_path.exists():
        st.error("Missing review.json or imposed.pdf in the latest job folder.")
        st.stop()

    review = read_json(review_path)

    pages = review["pages"]  # list of dicts
    suggested_exclude: Set[int] = set(review.get("suggested_exclude_indices", []))

    def _set_all_checkboxes(val: bool) -> None:
        for i in range(len(pages)):
            st.session_state[f"print_{i}"] = val

    # iPhone convenience
    st.subheader("Open on iPhone (same Wi-Fi)")
    url_hint = _lan_hint_url()
    st.write(f"Use: `{url_hint}`")
    st.image(
        _qr_png_bytes(url_hint),
        width=220,
        caption="Optional: scan QR, then replace <LAN-IP> with your laptop IP",
    )
    st.divider()

    # --- Load thumbnails


    st.subheader("Select pages to PRINT (greyed out = excluded)")

    # Controls
    colA, colB, colC = st.columns(3)
    with colA:
        if st.button("Select all"):
            _set_all_checkboxes(True)
            st.session_state["print_set"] = set(range(len(pages)))
            st.rerun()
    with colB:
        if st.button("Select none"):
            _set_all_checkboxes(False)
            st.session_state["print_set"] = set()
            st.rerun()
    with colC:
        if st.button("Apply suggestions"):
            keep = set(range(len(pages))) - set(suggested_exclude)
            _set_all_checkboxes(False)
            for i in keep:
                st.session_state[f"print_{i}"] = True   
            st.session_state["print_set"] = keep
            st.rerun()

    # Initialize print_set once
    if "print_set" not in st.session_state:
        st.session_state["print_set"] = set(range(len(pages))) - set(suggested_exclude)

    print_set = set(st.session_state["print_set"])

    # Grid display
    cols_per_row = 2
    for row_start in range(0, len(pages), cols_per_row):
        cols = st.columns(cols_per_row, gap="small")

        for j in range(cols_per_row):
            i = row_start + j
            if i >= len(pages):
                break

            p = pages[i]
            tp = thumbs_dir / f"page_{i:03d}.png"

            with cols[j]:
                # Page label + checkbox on one line
                h1, h2 = st.columns([10, 1], gap="small")

                with h1:
                    st.caption(p["page_id"])
                with h2:
                    printed = st.checkbox(
                        "Print",
                        key=f"print_{i}",
                        label_visibility="collapsed",
                    )

                # Sync print_set
                if printed:
                    print_set.add(i)
                else:
                    print_set.discard(i)

                # Thumbnail opacity
                opacity = 1.0 if printed else 0.30

                # Thumbnail (FULL WIDTH)
                if tp.exists():
                    uri = _thumb_data_uri(tp)
                    st.markdown(
                        f"""
                        <img
                            src="{uri}"
                            style="width:100%; border-radius:10px; opacity:{opacity}; display:block;"
                        />
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning("Thumbnail missing")

    st.session_state["print_set"] = print_set

    # Persist selection and compute excludes
    included_indices = sorted(print_set)
    exclude_indices = sorted(set(range(len(pages))) - print_set)

    st.divider()
    st.subheader("Summary")

    st.write(f"Included pages: **{len(included_indices)}** / {len(pages)}")
    st.code(", ".join([pages[i]["page_id"] for i in included_indices]) if included_indices else "(none)")

    st.write(f"Excluded pages: **{len(exclude_indices)}**")
    st.code(", ".join([pages[i]["page_id"] for i in exclude_indices]) if exclude_indices else "(none)")

    st.session_state["print_set"] = print_set

    st.divider()
    st.subheader("Finalize")

    st.write(f"Pages to exclude: **{len(exclude_indices)}**")
    st.code(", ".join([pages[i]["page_id"] for i in exclude_indices]) if exclude_indices else "(none)")

    if st.button("Generate FINAL print PDF", type="primary"):
        imposed_bytes = imposed_path.read_bytes()
        final_bytes = exclude_pages_by_index(imposed_bytes, exclude_indices)

        final_path = job_dir / "final_print.pdf"
        final_path.write_bytes(final_bytes)

        # Optional: excluded-only pdf
        ex_writer = PdfWriter()
        r = PdfReader(BytesIO(imposed_bytes))
        for i in exclude_indices:
            ex_writer.add_page(r.pages[i])
        ex_buf = BytesIO()
        ex_writer.write(ex_buf)
        (job_dir / "excluded_only.pdf").write_bytes(ex_buf.getvalue())

        # Log decisions
        write_json(
            job_dir / "decisions.json",
            {
                "job": job_dir.name,
                "excluded_indices": exclude_indices,
                "excluded_page_ids": [pages[i]["page_id"] for i in exclude_indices],
                "suggested_excluded_indices": sorted(suggested_exclude),
            },
        )

        st.success(f"Generated: {final_path}")
        st.write("Open the folder and print the final PDF.")


if __name__ == "__main__":
    main()
