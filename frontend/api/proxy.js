export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req, res) {
  try {
    const parsed = new URL(req.url, "http://localhost");

    // Extract the backend path from Vercel rewrite
    let subPath = parsed.searchParams.get("__path") || "";

    // Clean path
    subPath = subPath.replace(/^\/+/, "");

    // Remove Vercel rewrite parameters
    parsed.searchParams.delete("__path");
    parsed.searchParams.delete("path");

    const queryString = parsed.searchParams.toString();

    // Construct Hugging Face backend URL
    const targetUrl = `https://hugtarsem-leaselens.hf.space/api/${subPath}${
      queryString ? `?${queryString}` : ""
    }`;

    // Forward headers
    const headers = { ...req.headers };

    delete headers.host;
    delete headers.connection;
    delete headers["content-length"];
    delete headers["transfer-encoding"];

    // Hugging Face backend
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
      originalUrl: req.url,
      subPath,
      targetUrl,
    });

    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });

    res.status(upstream.status);

    // Forward response headers
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