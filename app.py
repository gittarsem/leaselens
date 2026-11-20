import gradio as gr
from api.server import app as fastapi_app

with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")

app = gr.mount_gradio_app(fastapi_app, demo, path="/")
