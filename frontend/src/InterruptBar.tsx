import type { InterruptItem } from "./researchModel";

type Props = {
  interrupts: InterruptItem[];
  busy: boolean;
  onResolve: (interruptId: string, resolution: string) => void;
  onCancel: () => void;
};

/** HITL dock — renders the backend's real prompt + options[], one action each. */
export default function InterruptBar({ interrupts, busy, onResolve, onCancel }: Props) {
  const first = interrupts[0];
  if (!first) return null;
  const options = first.options.length ? first.options : ["approve", "reject"];

  return (
    <div className="interrupt" role="alert" aria-label="需要你确认">
      <div className="interrupt-head">
        <span className="interrupt-kicker">需要你确认</span>
        {first.kind ? <span className="muted interrupt-kind">{first.kind}</span> : null}
      </div>
      <p className="interrupt-prompt">{first.prompt || "请选择下一步动作"}</p>
      {interrupts.length > 1 ? (
        <p className="muted interrupt-more">另有 {interrupts.length - 1} 个待处理中断</p>
      ) : null}
      <div className="row-actions">
        {options.map((opt, i) => (
          <button
            key={opt}
            type="button"
            className={i === 0 ? "" : "ghost"}
            disabled={busy}
            onClick={() => onResolve(first.id, opt)}
          >
            {opt}
          </button>
        ))}
        <button type="button" className="ghost danger" disabled={busy} onClick={onCancel}>
          取消任务
        </button>
      </div>
    </div>
  );
}
