import { useCallback, useEffect, useState } from "react";
import { fetchHouseholds, type HouseholdSummary } from "../../api/financial";

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

export function useSpecializedHouseholdView<T>(
  loader: (householdId: string, signal?: AbortSignal) => Promise<T>,
  preferredCase: string,
) {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [view, setView] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHouseholds = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchHouseholds(signal);
      if (items.length === 0) throw new Error("尚无可分析家庭");
      setHouseholds(items);
      const requested = requestedCaseCode();
      const preferred = items.find((item) => item.code === requested)
        ?? items.find((item) => item.code === preferredCase)
        ?? items[0];
      if (preferred) setHouseholdId(preferred.id);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setLoading(false);
      setError("无法读取家庭资料，请检查服务后重试。");
    }
  }, [preferredCase]);

  const loadView = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    setError(null);
    if (options.force) setRefreshing(true);
    else setLoading(true);
    try {
      setView(await loader(selectedHouseholdId, options.signal));
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setView(null);
      setError(loadError instanceof Error ? loadError.message : "专业方案读取失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [loader]);

  useEffect(() => {
    const controller = new AbortController();
    void loadHouseholds(controller.signal);
    return () => controller.abort();
  }, [loadHouseholds]);

  useEffect(() => {
    if (!householdId) return;
    const controller = new AbortController();
    void loadView(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadView]);

  return {
    households,
    householdId,
    setHouseholdId,
    selectedHousehold: households.find((item) => item.id === householdId),
    view,
    loading,
    refreshing,
    error,
    loadHouseholds,
    loadView,
  };
}
