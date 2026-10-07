import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "知芽 · 陪你读懂成长",
  description: "0-3 岁家庭的科学育儿与亲子故事助手",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body suppressHydrationWarning><AppShell>{children}</AppShell></body></html>;
}
