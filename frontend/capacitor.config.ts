import type { CapacitorConfig } from "@capacitor/cli";

// 安卓内测：让 App 的 WebView 加载本机开发服务器（含 /api 同源代理）。
// 局域网 IP 变化时改这里，或通过 CAPACITOR_SERVER_URL 覆盖。
const serverUrl = process.env.CAPACITOR_SERVER_URL ?? "http://192.168.120.57:3001";

const config: CapacitorConfig = {
  appId: "com.kidsmind.app",
  appName: "知芽",
  webDir: "public",
  server: {
    url: serverUrl,
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
