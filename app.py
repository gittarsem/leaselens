import os
import threading
import uvicorn
import spaces
import gradio as gr
from fastapi import Request
from fastapi.responses import Response
import httpx
from api.server import app as fastapi_app

@spaces.GPU
def warmup():
    return "ready"

with gr.Blocks() as demo:
    gr.Markdown("# LeaseLens API is live")
    btn = gr.Button("Warmup")
    btn.click(fn=warmup, outputs=gr.Textbox())

def _run_fastapi():
    uvicorn.run(fastapi_app, host="127.0.0.1", port=7862, log_level="info")

threading.Thread(target=_run_fastapi, daemon=True).start()

_orig_create_app = gr.routes.App.create_app

def _patched_create_app(blocks, *args, **kwargs):
    gradio_app = _orig_create_app(blocks, *args, **kwargs)

    @gradio_app.middleware("http")
    async def forward_api_to_fastapi(request: Request, call_next):
        if request.url.path.startswith("/api"):
            target = f"http://127.0.0.1:7862{request.url.path}"
            if request.url.query:
                target += f"?{request.url.query}"
            body = await request.body()
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length", "connection")
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.request(
                    method=request.method,
                    url=target,
                    headers=headers,
                    content=body,
                )
            resp_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "transfer-encoding", "connection")
            }
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp_headers,
            )
        return await call_next(request)

    return gradio_app

gr.routes.App.create_app = _patched_create_app

demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
)
