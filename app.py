import os
import asyncio
from contextlib import AsyncExitStack
import spaces
import gradio as gr
from api.server import app as fastapi_app

_orig_launch = gr.Blocks.launch

def _custom_launch(self, *args, **kwargs):
    kwargs["prevent_thread_lock"] = True
    res = _orig_launch(self, *args, **kwargs)
    self.app.mount("/backend", fastapi_app)
    self.app.router.routes.insert(0, self.app.router.routes.pop())
    self.block_thread()
    return res

gr.Blocks.launch = _custom_launch

@spaces.GPU
def warmup():
    return "ready"

with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    btn = gr.Button("Warmup")
    btn.click(fn=warmup, outputs=gr.Textbox())

_lifespan_stack = AsyncExitStack()
asyncio.run(_lifespan_stack.enter_async_context(fastapi_app.router.lifespan_context(fastapi_app)))

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
    )
