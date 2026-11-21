export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req, res) {
  try {
    const parsed = new URL(req.url, "http://localhost");

    // Extract the actual backend path from Vercel rewrite
    const subPath = parsed.searchParams.get("__path") || "";

    // Remove internal rewrite parameter
    parsed.searchParams.delete("__path");

    const queryString = parsed.searchParams.toString();

    // Hugging Face FastAPI backend
    const targetUrl = `https://hugtarsem-leaselens.hf.space/api/${subPath}${
      queryString ? `?${queryString}` : ""
    }`;

    // Forward request headers
    const headers = { ...req.headers };

    delete headers.host;
    delete headers.connection;
    delete headers["content-length"];

    // Avoid Gradio frontend interception
    headers.origin = "https://hugtarsem-leaselens.hf.space";
    headers.referer = "https://hugtarsem-leaselens.hf.space/";

    const hasBody = !["GET", "HEAD"].includes(req.method);

    let body;

    if (hasBody) {
      const chunks = [];

      for await (const chunk of req) {
        chunks.push(chunk);
      }

      body = Buffer.concat(chunks);
    }

    console.log("Proxy request:", {
      method: req.method,
      targetUrl,
    });

    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });

    // Forward status
    res.status(upstream.status);

    // Forward headers
    upstream.headers.forEach((value, key) => {
      const excludedHeaders = [
        "content-encoding",
        "transfer-encoding",
        "connection",
      ];

      if (!excludedHeaders.includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });

    // Forward response body
    const responseBuffer = Buffer.from(
      await upstream.arrayBuffer()
    );

    res.send(responseBuffer);

  } catch (error) {
    console.error("Proxy error:", error);

    res.status(500).json({
      error: "Proxy error",
      message: error.message,
    });
  }
}