import { InkButton } from "../../components/ink/Ink";
import type { AgentRunAction } from "./AgentRunPage";

// Approval-class actions (resume/retry approve the run continuing) are cinnabar
// right-angle seal buttons; pause/cancel stay plain ink buttons. No control here
// writes a ChapterVersion — they only hit the agent-run control endpoints.
const CONTROL_TONES: Record<AgentRunAction, "default" | "vermilion"> = { pause: "default", resume: "vermilion", cancel: "default", retry: "vermilion" };

export function AgentRunControls({ onAction }: { onAction: (action: AgentRunAction) => void }) {
  return <div aria-label="Agent run controls" style={{ display: "flex", gap: 8 }}>
    {(["pause", "resume", "cancel", "retry"] as const).map(action => <InkButton key={action} type="button" tone={CONTROL_TONES[action]} onClick={() => onAction(action)}>{action}</InkButton>)}
  </div>;
}
