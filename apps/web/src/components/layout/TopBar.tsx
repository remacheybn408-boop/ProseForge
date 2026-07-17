export function TopBar({ title = "ProseForge" }: { title?: string }) { return <header className="workspace-topbar"><span className="eyebrow">CURRENT PROJECT</span><strong>{title}</strong></header>; }
