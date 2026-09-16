import { useNavigate } from "react-router-dom";

export function StatTile({
  label,
  value,
  sub,
  to,
}: {
  label: string;
  value: string | number;
  sub?: string;
  to?: string;
}) {
  const navigate = useNavigate();
  return (
    <div
      className="stat-tile"
      onClick={() => to && navigate(to)}
      role={to ? "button" : undefined}
      tabIndex={to ? 0 : undefined}
    >
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub ? <div className="sub">{sub}</div> : null}
    </div>
  );
}
