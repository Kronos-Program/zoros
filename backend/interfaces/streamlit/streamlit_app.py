# See architecture: docs/zoros_architecture.md#ui-blueprint
import json
import uuid
from pathlib import Path

import streamlit as st

from ...persistence import (
    load_thread,
    load_fiber,
    resolveFiber,
    Fiber,
    UI_STATE_DIR,
)

THREAD_ID = "thread-wastelander-part2"
STATE_FILE = UI_STATE_DIR / "part2_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


thread = load_thread(THREAD_ID)
state = load_state()

st.title("Wastelander Part 2 Review")

for idx, fid in enumerate(thread["fiber_ids"], 1):
    fiber = load_fiber(fid)
    expanded = state.get(fid, False)
    with st.expander(f"{fiber['type']} {idx}", expanded=expanded):
        st.write(fiber["content"])
        current = st.session_state.get(f"exp_{fid}", expanded)
        state[fid] = current

save_state(state)

if st.button("Accept"):
    ann = Fiber(
        fiber_id=str(uuid.uuid4()),
        type="AnnotationFiber",
        content="ui-accept-part2",
        source="streamlit",
    )
    resolveFiber(ann)
    st.success("Accepted")
