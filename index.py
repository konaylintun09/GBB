"""Vercel serverless entrypoint — exposes the FastAPI app as a single Vercel Function."""
import os
import sys

# make the repo root importable so the `app` package resolves on Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402  (Vercel's Python runtime serves this ASGI `app`)
