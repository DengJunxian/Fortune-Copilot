import { useDisplayPreferences } from "../../contexts/displayPreferences";

export function ClientPreferences() {
  const preferences = useDisplayPreferences();
  return (
    <section className="client-preferences" aria-label="显示与理解模式">
      <div className="preference-group">
        <span>主题</span>
        <div role="group" aria-label="主题模式">
          <button type="button" aria-pressed={preferences.theme === "light"} onClick={() => preferences.setTheme("light")}>浅色</button>
          <button type="button" aria-pressed={preferences.theme === "dark"} onClick={() => preferences.setTheme("dark")}>深色</button>
        </div>
      </div>
      <label className="preference-check">
        <input type="checkbox" checked={preferences.largeText} onChange={(event) => preferences.setLargeText(event.target.checked)} />
        <span>大字模式</span>
      </label>
      <label className="preference-check">
        <input type="checkbox" checked={preferences.plainLanguage} onChange={(event) => preferences.setPlainLanguage(event.target.checked)} />
        <span>低金融知识模式</span>
      </label>
      <label className="preference-check">
        <input type="checkbox" checked={preferences.maskAmounts} onChange={(event) => preferences.setMaskAmounts(event.target.checked)} />
        <span>隐藏金额</span>
      </label>
      <div className="preference-group">
        <span>数值视图</span>
        <div role="group" aria-label="数值显示方式">
          <button type="button" aria-pressed={preferences.valueView === "amount"} onClick={() => preferences.setValueView("amount")}>金额</button>
          <button type="button" aria-pressed={preferences.valueView === "ratio"} onClick={() => preferences.setValueView("ratio")}>比例</button>
        </div>
      </div>
      <label className="preference-select">
        <span>金额单位</span>
        <select value={preferences.moneyUnit} onChange={(event) => preferences.setMoneyUnit(event.target.value as "yuan" | "wan")}>
          <option value="yuan">元</option>
          <option value="wan">万元</option>
        </select>
      </label>
    </section>
  );
}
