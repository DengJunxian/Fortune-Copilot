/** Fortune Copilot's owned semantic chart palette, mirrored from DESIGN.md. */
export interface ChartTheme {
  brand: string;
  action: string;
  goal: string;
  warning: string;
  muted: string;
  surface: string;
  textMuted: string;
  text: string;
  brandWash: string;
  brandWashStrong: string;
}

export const chartTheme: ChartTheme = {
  brand: "#315d7d",
  action: "#a61d2d",
  goal: "#9a762e",
  warning: "#a94f16",
  muted: "#9babb5",
  surface: "#d5dde2",
  textMuted: "#52636f",
  text: "#17242d",
  brandWash: "rgba(49,93,125,0.18)",
  brandWashStrong: "rgba(49,93,125,0.30)",
};

export const darkChartTheme: ChartTheme = {
  brand: "#82b4d1",
  action: "#f06c77",
  goal: "#d8b66d",
  warning: "#f0a06a",
  muted: "#8ea0aa",
  surface: "#324550",
  textMuted: "#bec9ce",
  text: "#edf2f3",
  brandWash: "rgba(130,180,209,0.18)",
  brandWashStrong: "rgba(130,180,209,0.30)",
};

export function chartThemeFor(theme: "light" | "dark"): ChartTheme {
  return theme === "dark" ? darkChartTheme : chartTheme;
}
