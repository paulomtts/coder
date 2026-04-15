export type LineAction =
  | { type: "quit" }
  | { type: "cancel" }
  | { type: "scroll-up" }
  | { type: "scroll-down" }
  | { type: "scroll-home" }
  | { type: "scroll-end" }
  | { type: "message"; text: string };

export function parseLineAction(line: string): LineAction {
  const trimmed = line.trim();
  const normalized = trimmed.toLowerCase();

  if (normalized === "/quit" || normalized === "/exit") return { type: "quit" };
  if (normalized === "/cancel" || normalized === "/k") return { type: "cancel" };
  if (normalized === "/up" || normalized === "/pageup") return { type: "scroll-up" };
  if (normalized === "/down" || normalized === "/pagedown") return { type: "scroll-down" };
  if (normalized === "/home" || normalized === "/top") return { type: "scroll-home" };
  if (normalized === "/end" || normalized === "/bottom") return { type: "scroll-end" };
  return { type: "message", text: line };
}
