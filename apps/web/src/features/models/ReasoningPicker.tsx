import { useRef } from "react";
import { REASONING_LEVELS, type ReasoningLevel } from "./modelCapabilities";

const DOTS: Record<ReasoningLevel, string> = { auto: "", fast: "●○○○○", standard: "●●○○○", deep: "●●●○○", max: "●●●●●" };
const UNSUPPORTED_REASON = "This model does not support adjustable reasoning; only auto is available.";
const NAV_KEYS = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"]);

export function ReasoningPicker({ value, supported, onChange }: { value: ReasoningLevel; supported: ReasoningLevel[]; onChange: (level: ReasoningLevel) => void }) {
  const valueUnsupported = !supported.includes(value);
  const buttons = useRef<Partial<Record<ReasoningLevel, HTMLButtonElement | null>>>({});
  const enabled = REASONING_LEVELS.filter(level => supported.includes(level));
  // APG radiogroup 漫游 tabindex：选中项在 Tab 序里，其余 -1；
  // 当前值不支持时由首个可用项接管 Tab 序（绝不静默改值）。
  const tabStop: ReasoningLevel | null = enabled.length === 0 ? null : (supported.includes(value) ? value : enabled[0]);

  const moveSelection = (from: ReasoningLevel, key: string) => {
    if (enabled.length === 0) return;
    const current = enabled.indexOf(from);
    let next: ReasoningLevel;
    if (key === "Home") next = enabled[0];
    else if (key === "End") next = enabled[enabled.length - 1];
    else {
      const delta = key === "ArrowRight" || key === "ArrowDown" ? 1 : -1;
      next = enabled[(Math.max(0, current) + delta + enabled.length) % enabled.length];
    }
    onChange(next); // selection follows focus；disabled 项不在 enabled 中自然跳过
    buttons.current[next]?.focus();
  };

  return <div className="reasoning-picker" role="radiogroup" aria-label="Reasoning strength">
    <span className="reasoning-picker-label">Reasoning</span>
    {REASONING_LEVELS.map(level => {
      const isSupported = supported.includes(level);
      return <button
        key={level}
        type="button"
        role="radio"
        ref={element => { buttons.current[level] = element; }}
        aria-checked={value === level}
        tabIndex={level === tabStop ? 0 : -1}
        className={`reasoning-level${value === level ? " selected" : ""}`}
        disabled={!isSupported}
        title={isSupported ? `${level} reasoning strength` : UNSUPPORTED_REASON}
        onClick={() => { if (isSupported) onChange(level); }}
        onKeyDown={event => {
          if (!NAV_KEYS.has(event.key)) return;
          event.preventDefault();
          moveSelection(level, event.key);
        }}>
        {DOTS[level] ? <span className="reasoning-dots" aria-hidden="true">{DOTS[level]}</span> : null}
        <span className="reasoning-name">{level}</span>
      </button>;
    })}
    {valueUnsupported ? <span className="reasoning-warning" role="status">Level “{value}” is not supported by this model — sending will be rejected (422). Pick a supported level.</span> : null}
  </div>;
}
