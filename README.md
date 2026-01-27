# climb-agent
Climbing training GOD

## UI-0 (Colab)

**Important (Colab):**
- Run Gradio in a **Python cell**, not `%%bash` (Colab often looks “stuck” on long-running servers).
- Bind to `127.0.0.1` (not `0.0.0.0`) to make Colab proxy/iframe reliable.
- Ensure `prevent_thread_lock=False` so the process stays alive.

Verified pipeline:
1) `%%bash`: `python scripts/run_baseline_session.py`
2) `%%bash`: `python scripts/generate_latest_log_template.py`
3) Python: start UI (keep process alive)
4) Python: `output.serve_kernel_port_as_iframe(...)`
