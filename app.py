import os
import asyncio
from contextlib import AsyncExitStack
from starlette.applications import Starlette
from api.server import app as fastapi_app

_orig_starlette_call = Starlette.__call__

async def _patched_starlette_call(self, scope, receive, send):
    if (
        self is not fastapi_app
        and scope.get("type") == "http"
        and scope.get("path", "").startswith("/api")
    ):
        await _orig_starlette_call(fastapi_app, scope, receive, send)
        return
    await _orig_starlette_call(self, scope, receive, send)

Starlette.__call__ = _patched_starlette_call

import spaces
import gradio as gr

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
)
