import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1"],
  // 照片转卡通等 AI 生成接口单次可达 30s+，默认代理超时 30s 会掐断请求；调到 180s 对齐后端 httpx 超时
  experimental: {
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/story_assets/:path*",
        destination: `${backendUrl}/story_assets/:path*`,
      },
      {
        source: "/avatars/:path*",
        destination: `${backendUrl}/avatars/:path*`,
      },
      {
        source: "/companion_assets/:path*",
        destination: `${backendUrl}/companion_assets/:path*`,
      },
    ];
  },
};

export default nextConfig;
