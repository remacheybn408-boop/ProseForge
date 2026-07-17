import type { ReactNode } from "react";
export function WorkspaceSplit({ children, inspector }: { children: ReactNode; inspector?: ReactNode }) { return <div className="workspace-split"><main>{children}</main><aside className="workspace-inspector">{inspector}</aside></div>; }
