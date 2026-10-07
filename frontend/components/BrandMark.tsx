"use client";

import { useId } from "react";

/**
 * 知芽品牌标识「心智萌芽」
 * 渐变种子形 + 负形幼苗，来自 kids-mind-brand/assets/logo-a-sprout.svg
 */
export function BrandMark({ size = 40, title }: { size?: number; title?: string }) {
  const raw = useId();
  const id = raw.replace(/[^a-zA-Z0-9]/g, "");
  const gradientId = `kmGradient-${id}`;
  const maskId = `kmSprout-${id}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={title ?? "知芽"}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={gradientId} x1="16" y1="6" x2="48" y2="58" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FF7A94" />
          <stop offset="1" stopColor="#FFB877" />
        </linearGradient>
        <mask id={maskId}>
          <rect width="64" height="64" fill="#FFFFFF" />
          <g fill="#000000">
            <path d="M31.4 36.5C25.6 36 21 31.2 22 24.4C27.7 23.9 31.4 29.6 31.4 36.5Z" />
            <path d="M32.6 32.6C38.4 32.1 42 27.3 41 20.5C35.3 20 32.6 25.7 32.6 32.6Z" />
            <path d="M32 46V27" stroke="#000000" strokeWidth="4.6" strokeLinecap="round" />
          </g>
        </mask>
      </defs>
      <path
        mask={`url(#${maskId})`}
        fill={`url(#${gradientId})`}
        d="M32 5C40.6 5 47 15.4 47 28C47 43 40.6 58 32 58C23.4 58 17 43 17 28C17 15.4 23.4 5 32 5Z"
      />
    </svg>
  );
}
