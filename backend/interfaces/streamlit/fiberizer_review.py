"""Streamlit UI for reviewing fibers after fiberization.

Each fiber is displayed in a collapsible card with edit capability.
See docs/tasks/TASK-79_streamlit-fiberizer-review.md for details.
"""
from __future__ import annotations

import json
import os
import uuid

import streamlit as st

# use absolute import so Streamlit can run this file directly
from source.persistence import load_thread, load_fiber, resolveFiber, Fiber, base_dir

UI_STATE_DIR = base_dir() / "ui_state"

# Thread to review, overridable for tests
THREAD_ID = os.getenv("REVIEW_THREAD_ID", "thread-wastelander-part2")
STATE_FILE = UI_STATE_DIR / f"{THREAD_ID}_state.json"


@st.cache_data
def _load_fibers(tid: str) -> list[dict]:
    thread = load_thread(tid)
    return [load_fiber(fid) for fid in thread["fiber_ids"]]


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


state = _load_state()
fibers = _load_fibers(THREAD_ID)

st.title("Fiberizer Review")

for idx, fiber in enumerate(fibers, 1):
    fid = fiber.get("fiber_id") or fiber.get("id", str(idx))
    expand_key = f"exp_{fid}"
    edit_key = f"edit_{fid}"
    expanded = state.get(expand_key, False)
    if st.button("Collapse" if expanded else "Expand", key=f"toggle_{fid}"):
        expanded = not expanded
    state[expand_key] = expanded
    with st.expander(f"{fiber.get('type', 'Fiber')} {idx}", expanded=expanded):
        st.markdown(f"**Fold:** {fiber.get('fold_level', 0)}")
        if st.session_state.get(edit_key, False):
            text = st.text_area("Edit Content", value=fiber.get("content", ""), key=f"ta_{fid}")
            if st.button("Save", key=f"save_{fid}"):
                ann = Fiber(
                    fiber_id=str(uuid.uuid4()),
                    type="AnnotationFiber",
                    content=text,
                    source="streamlit",
                )
                resolveFiber(ann)
                st.session_state[edit_key] = False
                st.success("Saved")
        else:
            st.write(fiber.get("content", ""))
            if st.button("Edit", key=f"edit_btn_{fid}"):
                st.session_state[edit_key] = True

_save_state(state)

if st.button("Finalize"):
    print(f"Finalize {THREAD_ID} with {len(fibers)} fibers")
    st.success("Finalized")
