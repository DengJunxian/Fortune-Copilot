import { useState } from "react";
import { Button } from "../ui/Button";

const states = {
  loading: ["正在加载", "正在读取家庭事实与规则版本。", "等待计算完成"],
  skeleton: ["结构骨架", "先保留最终布局，避免页面跳动。", "继续等待"],
  empty: ["暂无数据", "当前范围没有可展示记录。", "补充家庭资料"],
  first_use: ["首次使用", "尚未完成隐私授权和家庭建档。", "开始授权"],
  missing_data: ["资料缺失", "缺少字段会影响部分指标或目标判断。", "补齐缺失项"],
  data_conflict: ["数据冲突", "同一事实存在不同版本，系统没有自行覆盖。", "逐项确认"],
  calculation_failed: ["计算失败", "确定性引擎未返回完整结果，页面不展示部分金额。", "重新计算"],
  model_degraded: ["模型降级", "外部模型不可用，已切换模板解释；确定性计算不受影响。", "查看边界"],
  permission_denied: ["权限不足", "当前角色没有读取或修改此范围的权限。", "申请人工授权"],
  offline: ["网络离线", "保留已缓存能力和 Mock 主流程，不调用外部服务。", "继续 Mock 演示"],
  stale_data: ["数据已过期", "数据日超出当前复核窗口，旧结果仍保留但不能直接执行。", "更新数据"],
  no_suitable_product: ["无适配产品", "适当性条件未通过，系统不会为了完成页面而强行匹配。", "查看教育说明"],
  compliance_blocked: ["方案被合规拦截", "规则命中后停止输出可执行建议。", "转人工复核"],
  report_failed: ["报告生成失败", "章节没有完整通过一致性检查。", "保留底稿并重试"],
} as const;

type PreviewState = keyof typeof states;

export function ClientStatePreview() {
  const [state, setState] = useState<PreviewState>("offline");
  const [message, setMessage] = useState("");
  const [title, reason, action] = states[state];
  return (
    <details className="client-state-preview">
      <summary>查看完整状态演示</summary>
      <p>以下仅用于合成 Demo 验证，不改变当前家庭数据。</p>
      <label>
        <span>状态</span>
        <select value={state} onChange={(event) => { setState(event.target.value as PreviewState); setMessage(""); }}>
          {Object.entries(states).map(([code, value]) => <option key={code} value={code}>{value[0]}</option>)}
        </select>
      </label>
      <section className="client-state-card" data-state={state} aria-live="polite">
        <strong>{title}</strong>
        <p>{reason}</p>
        <Button type="button" variant="secondary" onClick={() => setMessage(`已演示操作：${action}`)}>{action}</Button>
        <button className="text-button" type="button" onClick={() => setMessage("已记录转人工入口演示。")}>转人工</button>
        {message ? <small role="status">{message}</small> : null}
      </section>
    </details>
  );
}
