import os

os.environ["GRADIO_SSR_MODE"] = "false"

import gradio as gr
import uvicorn
from fastapi import FastAPI

from api.server import app as backend_app


# Gradio UI
with gr.Blocks(title="LeaseLens") as demo:
    gr.Markdown("# ⚖️ LeaseLens")
    gr.Markdown("AI-powered lease analysis and tenant assistance.")

    gr.Markdown("### Backend Status")
    gr.Markdown("FastAPI backend is available under `/api`.")


# Create the main FastAPI application
app = FastAPI(title="LeaseLens")


# Mount backend API
app.mount("/api", backend_app)


# Mount Gradio UI at root
app = gr.mount_gradio_app(app, demo, path="/")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860
    )