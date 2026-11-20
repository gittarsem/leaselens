import os
import asyncio
from contextlib import AsyncExitStack
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

_lifespan_stack = AsyncExitStack()
asyncio.run(_lifespan_stack.enter_async_context(fastapi_app.router.lifespan_context(fastapi_app)))

demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
    prevent_thread_lock=True,
)
demo.app.mount("/backend", fastapi_app)
demo.app.router.routes.insert(0, demo.app.router.routes.pop())
demo.block_thread()
