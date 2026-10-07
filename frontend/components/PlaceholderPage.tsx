import Link from "next/link";
import { ArrowLeft, Sparkles } from "lucide-react";

export function PlaceholderPage({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="placeholder-page"><span className="placeholder-icon"><Sparkles size={26} /></span><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p><div className="stage-pill">首页代表页确认后，下一阶段将接入真实业务闭环</div><Link href="/" className="button secondary"><ArrowLeft size={17} />回到首页</Link></div>;
}
