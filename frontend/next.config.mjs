/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy API calls to the FastAPI backend so the browser only ever talks to
  // one origin (works in dev and in production behind the same host).
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
