export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req, res) {
  const parsed = new URL(req.url, "http://localhost");
  const subPath = parsed.searchParams.get("__path") || "";
  parsed.searchParams.delete("__path");
  const qs = parsed.searchParams.toString();
  const targetUrl = `https://hugtarsem-leaselens.hf.space/${subPath}${qs ? `?${qs}` : ""}`;
  const headers = { ...req.headers };
  delete headers.host;
  delete headers.connection;
  delete headers["content-length"];
  headers.origin = "https://hugtarsem-leaselens.hf.space";
  headers.referer = "https://hugtarsem-leaselens.hf.space/";

  const hasBody = !["GET", "HEAD"].includes(req.method);
  const chunks = [];
  if (hasBody) {
    for await (const chunk of req) {
      chunks.push(chunk);
    }
  }

  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers,
    body: hasBody ? Buffer.concat(chunks) : undefined,
  });

  res.status(upstream.status);
  upstream.headers.forEach((value, key) => {
    if (!["content-encoding", "transfer-encoding", "connection"].includes(key.toLowerCase())) {
      res.setHeader(key, value);
    }
  });

  const arrayBuffer = await upstream.arrayBuffer();
  res.send(Buffer.from(arrayBuffer));
}
