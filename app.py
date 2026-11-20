import os
import asyncio
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

asyncio.run(fastapi_app.router.startup())

demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
    prevent_thread_lock=True,
)

_gradio_stack = demo.app.middleware_stack or demo.app.build_middleware_stack()

async def _dispatch(scope, receive, send):
    if scope["type"] == "http" and scope.get("path", "").startswith("/api"):
        await fastapi_app(scope, receive, send)
    else:
        await _gradio_stack(scope, receive, send)

demo.app.middleware_stack = _dispatch
demo.block_thread()
