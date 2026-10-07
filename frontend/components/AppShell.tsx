"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookHeart, CircleUserRound, Crown, HeartHandshake, Home, LoaderCircle, MessageCircleHeart, Sprout } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { isLoggedIn } from "@/lib/auth";
import { BrandMark } from "./BrandMark";
import { LoginPage } from "./LoginPage";

const navigation = [
  { href: "/", label: "首页", icon: Home },
  { href: "/ask", label: "问育儿", icon: MessageCircleHeart },
  { href: "/growth", label: "成长", icon: Sprout },
  { href: "/stories", label: "故事", icon: BookHeart },
  { href: "/companion", label: "陪伴", icon: HeartHandshake },
  { href: "/membership", label: "会员", icon: Crown },
  { href: "/profile", label: "我的", icon: CircleUserRound },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [loggedIn, setLoggedIn] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoggedIn(isLoggedIn());
      setChecking(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (checking) {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在进入知芽…</strong></div>;
  }

  if (!loggedIn) {
    return <LoginPage onLoggedIn={() => setLoggedIn(true)} />;
  }

  return (
    <div className="app-frame">
      <aside className="sidebar" aria-label="主导航">
        <Link href="/" className="brand" aria-label="知芽首页">
          <span className="brand-mark"><BrandMark size={38} /></span>
          <span>
            <strong>知芽</strong>
            <small>陪你读懂成长</small>
          </span>
        </Link>
        <nav className="side-nav">
          {navigation.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className={active ? "nav-item active" : "nav-item"}>
                <Icon size={20} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <span className="note-dot" />
          <div><strong>科学育儿助手</strong><small>建议不能替代专业诊疗</small></div>
        </div>
      </aside>

      <main className="main-content">{children}</main>

      <nav className="bottom-nav" aria-label="移动端主导航">
        {navigation.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className={active ? "bottom-item active" : "bottom-item"}>
              <Icon size={21} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
