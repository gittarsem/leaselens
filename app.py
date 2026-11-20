import os
import spaces
import gradio as gr
from api.server import app as fastapi_app


@spaces.GPU
def warmup():
    return "ready"


with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    btn = gr.Button("Warmup")
    output = gr.Textbox()
    btn.click(fn=warmup, outputs=output)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
        app=fastapi_app,
    )
