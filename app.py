import os
import spaces
import gradio as gr
import uvicorn

from api.server import app as fastapi_app


@spaces.GPU
def warmup():
    return "ready"


with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    gr.Markdown("FastAPI backend is running.")

    btn = gr.Button("Warmup")
    output = gr.Textbox(label="Status")

    btn.click(fn=warmup, outputs=output)


# Mount Gradio UI onto FastAPI
fastapi_app = gr.mount_gradio_app(
    fastapi_app,
    demo,
    path="/",
)


if __name__ == "__main__":
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
    )