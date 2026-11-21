import os

# =========================================================
# Force CPU-only execution before importing ML dependencies
# =========================================================

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GRADIO_SSR_MODE"] = "false"

# =========================================================
# Imports
# =========================================================

import gradio as gr
import uvicorn
from fastapi import FastAPI

from api.server import app as backend_app


# =========================================================
# Gradio UI
# =========================================================

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


# =========================================================
# Main FastAPI Application
# =========================================================

app = FastAPI(
    title="LeaseLens Host",
    version="1.0.0",
)


# =========================================================
# Host Health Check
# =========================================================

@app.get("/host-health")
def host_health():
    return {
        "status": "ok",
        "application": "LeaseLens",
        "backend": "/api",
    }


# =========================================================
# Mount Backend API
# =========================================================

app.mount(
    "/api",
    backend_app,
)


# =========================================================
# Mount Gradio UI
# =========================================================

app = gr.mount_gradio_app(
    app,
    demo,
    path="/",
)


# =========================================================
# Application Entry Point
# =========================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "GRADIO_SERVER_PORT",
                os.environ.get("PORT", 7860),
            )
        ),
    )