import { REASONING_LEVELS, type ReasoningLevel } from "./modelCapabilities";

const DOTS: Record<ReasoningLevel, string> = { auto: "", fast: "●○○○", standard: "●●○○", deep: "●●●○", max: "●●●●" };
const UNSUPPORTED_REASON = "This model does not support adjustable reasoning; only auto is available.";

export function ReasoningPicker({ value, supported, onChange }: { value: ReasoningLevel; supported: ReasoningLevel[]; onChange: (level: ReasoningLevel) => void }) {
  const valueUnsupported = !supported.includes(value);
  return <div className="reasoning-picker" role="radiogroup" aria-label="Reasoning strength">
    <span className="reasoning-picker-label">Reasoning</span>
    {REASONING_LEVELS.map(level => {
      const isSupported = supported.includes(level);
      return <button
        key={level}
        type="button"
        role="radio"
        aria-checked={value === level}
        className={`reasoning-level${value === level ? " selected" : ""}`}
        disabled={!isSupported}
        title={isSupported ? `${level} reasoning strength` : UNSUPPORTED_REASON}
        onClick={() => { if (isSupported) onChange(level); }}>
        {DOTS[level] ? <span className="reasoning-dots" aria-hidden="true">{DOTS[level]}</span> : null}
        <span className="reasoning-name">{level}</span>
      </button>;
    })}
    {valueUnsupported ? <span className="reasoning-warning" role="status">Level “{value}” is not supported by this model — sending will be rejected (422). Pick a supported level.</span> : null}
  </div>;
}
