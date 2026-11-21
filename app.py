import os

# =========================================================
# CPU-only configuration for AI inference
# =========================================================

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# =========================================================
# Imports
# =========================================================

import gradio as gr
import spaces
import uvicorn
from fastapi import FastAPI

from api.server import app as backend_app


# =========================================================
# ZeroGPU Compatibility Function
# =========================================================

@spaces.GPU
def zerogpu_compatibility():
    """
    Lightweight function to satisfy ZeroGPU startup requirements.

    LeaseLens AI inference uses Gemini APIs and does not require
    local GPU computation.
    """
    return "LeaseLens is running. AI inference is handled by Gemini API."


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
        AI processing is powered by Gemini API.
        """
    )

    status_button = gr.Button("Check Application Status")
    status_output = gr.Textbox(label="Status")

    status_button.click(
        fn=zerogpu_compatibility,
        outputs=status_output,
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

app.mount("/api", backend_app)


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