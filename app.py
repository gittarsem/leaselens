import spaces
import gradio as gr
from api.server import app as fastapi_app

@spaces.GPU
def warmup():
    return "ready"

with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    btn = gr.Button("Warmup")
    out = gr.Textbox()
    btn.click(fn=warmup, outputs=out)

app = gr.mount_gradio_app(fastapi_app, demo, path="/")
