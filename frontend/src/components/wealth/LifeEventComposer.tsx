import { CheckIcon, TrendDownIcon } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import type { TwinState } from "../../api/persistentTwin";
import { Button } from "../ui/Button";

interface Props {
  members: TwinState["facts"]["members"];
  submitting: boolean;
  onSubmit: (input: { eventDate: string; memberId: string | null; ratio: string }) => Promise<void>;
}

function localToday(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function LifeEventComposer({ members, submitting, onSubmit }: Props) {
  const [eventDate, setEventDate] = useState(localToday());
  const [memberId, setMemberId] = useState("");
  const [percent, setPercent] = useState("-30");
  const [confirmed, setConfirmed] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmed) return;
    await onSubmit({
      eventDate,
      memberId: memberId || null,
      ratio: (Number(percent) / 100).toFixed(6),
    });
  }

  return (
    <section className="twin-event-composer" id="life-event-composer" aria-labelledby="life-event-title">
      <div className="twin-composer-copy">
        <span><TrendDownIcon size={19} weight="bold" aria-hidden="true" /> 录入已发生事件</span>
        <h2 id="life-event-title">工资收入发生变化</h2>
        <p>提交后会修改所选就业收入事实，并重新计算画像、需求、责任与 ELTC。重复提交完全相同的事件不会再次扣减。</p>
      </div>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <label>生效日期<input type="date" value={eventDate} max={localToday()} onChange={(event) => setEventDate(event.target.value)} required /></label>
        <label>影响成员<select value={memberId} onChange={(event) => setMemberId(event.target.value)}><option value="">全体工资收入</option>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name} · {member.relationship}</option>)}</select></label>
        <label>工资变动（%）<input type="number" min="-100" max="100" step="1" value={percent} onChange={(event) => setPercent(event.target.value)} required /></label>
        <label className="twin-confirm-row"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span><CheckIcon size={16} aria-hidden="true" /> 我确认这是已发生且需要写入家庭事实的变化</span></label>
        <Button type="submit" loading={submitting} disabled={!confirmed || Number(percent) === 0}>确认并生成新快照</Button>
      </form>
    </section>
  );
}
