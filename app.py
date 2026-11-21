import os

os.environ["GRADIO_SSR_MODE"] = "false"

import gradio as gr
import uvicorn

from fastapi import FastAPI
from api.server import app as backend_app


# -----------------------------
# Gradio UI
# -----------------------------
with gr.Blocks(title="LeaseLens") as demo:
    gr.Markdown(
        """
        # ⚖️ LeaseLens

        AI-powered lease analysis and tenant assistance.
        """
    )

    gr.Markdown(
        """
        ### Backend Status

        FastAPI backend is available under `/api`.
        """
    )


# -----------------------------
# Main FastAPI application
# -----------------------------
host_app = FastAPI(title="LeaseLens Host")


# Mount backend API
host_app.mount("/api", backend_app)


# Mount Gradio UI
app = gr.mount_gradio_app(
    host_app,
    demo,
    path="/"
)


# -----------------------------
# Start server
# -----------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860
    )