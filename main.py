"""
ProspectIQ v3.0 — Root CLI Entrypoint.

Thin backwards-compatible wrapper forwarding `python main.py ...` and GitHub Actions
invocations cleanly into `engine.main`.
"""

from engine.main import main

if __name__ == "__main__":
    main()
