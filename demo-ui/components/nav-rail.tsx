import { useSyncExternalStore } from "react";
import { nextTheme, readTheme, saveTheme, subscribeTheme, type ThemePreference } from "@/lib/theme";

const destinations = [
  { href: "#live", short: "LV", label: "Live" },
  { href: "#graph", short: "GR", label: "Graph" },
  { href: "#runs", short: "RN", label: "Runs" },
  { href: "#chat", short: "CH", label: "Chat" },
  { href: "#proposal", short: "PR", label: "Proposal" },
];

export function NavRail() {
  const theme = useSyncExternalStore<ThemePreference>(subscribeTheme, readTheme, () => "dark");
  const changeTheme = () => {
    const next = nextTheme(theme);
    saveTheme(next);
  };
  return <nav className="nav-rail" aria-label="Dashboard sections">
    <a className="rail-brand" href="#live" aria-label="Lab demo, về đầu dashboard">L<span>3</span></a>
    <div className="rail-links">{destinations.map((item) => <a href={item.href} className="rail-link" key={item.href}><span className="rail-short" aria-hidden="true">{item.short}</span><span>{item.label}</span></a>)}</div>
    <button type="button" className="theme-toggle" onClick={changeTheme} aria-label={`Theme hiện tại ${theme}; bấm để đổi theme`} title="Đổi theme: dark / light / system"><span aria-hidden="true">◐</span><span>{theme}</span></button>
  </nav>;
}
