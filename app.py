import spaces
import gradio as gr
from api.server import app as fastapi_app

@spaces.GPU
def warmup():
    return "ready"

with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    btn = gr.Button("Warmup")
    btn.click(fn=warmup, outputs=gr.Textbox())

demo.launch(server_name="0.0.0.0", server_port=7860, prevent_thread_lock=True)
demo.app.include_router(fastapi_app.router)
demo.block_thread()
