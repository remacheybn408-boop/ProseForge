import { useEffect, useState, type ReactNode } from "react";
import { useChatStore } from "../../features/chat/chatStore";

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => typeof window.matchMedia === "function" ? window.matchMedia(query).matches : false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export function WorkspaceSplit({ children, inspector }: { children: ReactNode; inspector?: ReactNode }) {
  const narrow = useMediaQuery("(max-width: 1000px)");
  const drawerOpen = useChatStore(state => state.inspectorOpen);
  return <div className="workspace-split">
    <main>{children}</main>
    {inspector !== undefined && <aside className={`workspace-inspector${narrow ? " drawer" : ""}${narrow && drawerOpen ? " open" : ""}`}>{inspector}</aside>}
  </div>;
}
