// Renders the 24-hour ELD activity graph exactly like the paper log form:
//   • 4 rows: Off Duty · Sleeper Berth · Driving · On Duty (Not Driving)
//   • Continuous line running horizontally on the active row,
//     dropping vertically at every activity transition
//   • Red dots at each transition point (start, change, end)
//   • Translucent colour fill under each active segment
//   • Tick marks at 15-min / 30-min / 1-hr intervals
//   • Hour labels: Midnight · 1 … Noon … 11 · Midnight

const LABEL_W    = 88;    // left label column width (viewBox units)
const ROW_H      = 36;    // height of each activity row
const HEADER_H   = 22;    // height of the hour-label header strip
const TOTAL_SLOTS = 96;   // 24 h × 4 slots/h
const DOT_R      = 3.5;   // radius of transition dots
const GRID_W     = 960;   // viewBox units for the 96-slot area
const SVG_W      = LABEL_W + GRID_W;
const SVG_H      = HEADER_H + 4 * ROW_H + 1;
const SLOT_W     = GRID_W / TOTAL_SLOTS; // 10 viewBox units per 15-min slot

// Row order matches paper form (top → bottom)
const ROW_ORDER  = ["OF", "SB", "D", "ON"];
const ROW_LABELS = {
  OF: "1: Off Duty",
  SB: "2: Sleeper\nBerth",
  D:  "3: Driving",
  ON: "4: On Duty\n(Not Driving)",
};
const ROW_COLORS = {
  OF: "#4caf7d",
  SB: "#9b7fe8",
  D:  "#f5a623",
  ON: "#5ba4cf",
};

// Y centre for a given activity row
const rowY  = (act) => HEADER_H + ROW_ORDER.indexOf(act) * ROW_H + ROW_H / 2;
// X position for a given slot index (0–96)
const slotX = (slot) => LABEL_W + slot * SLOT_W;

// Hour labels array (0–24)
const HOUR_LABELS = Array.from({ length: 25 }, (_, h) => ({
  h,
  label: h === 0 || h === 24 ? "Mid" : h === 12 ? "Noon" : String(h <= 12 ? h : h - 12),
}));

export default function ActivityGrid({ actLogs, day }) {
  // ── Parse actLogs → sorted segments within this day ────────
  const segments = [];
  if (actLogs && day) {
    const dayStart = new Date(day + "T00:00:00Z");
    actLogs
      .slice()
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
      .forEach(act => {
        if (!ROW_COLORS[act.activity]) return;
        const startSlot = Math.max(0,  (new Date(act.start_time) - dayStart) / (15 * 60000));
        const endSlot   = Math.min(TOTAL_SLOTS, (new Date(act.end_time) - dayStart) / (15 * 60000));
        if (endSlot > startSlot) segments.push({ activity: act.activity, startSlot, endSlot });
      });
  }

  // ── Build polyline, fill rects, and transition dots ────────
  const polyPoints = []; // flat [x, y, x, y, …]
  const dots       = []; // [{x, y}]
  const fills      = []; // [{activity, x, y, width, height}]

  if (segments.length > 0) {
    let curAct = segments[0].activity;
    let cx = slotX(segments[0].startSlot);
    let cy = rowY(curAct);
    polyPoints.push(cx, cy);
    dots.push({ x: cx, y: cy });

    segments.forEach(seg => {
      const sx = slotX(seg.startSlot);
      const ex = slotX(seg.endSlot);
      const sy = rowY(seg.activity);

      // Activity changed or gap → vertical connector
      if (Math.abs(sx - polyPoints[polyPoints.length - 2]) > 0.5 || seg.activity !== curAct) {
        if (sx > polyPoints[polyPoints.length - 2] + 0.5) polyPoints.push(sx, cy);
        if (sy !== cy) {
          dots.push({ x: sx, y: cy });
          polyPoints.push(sx, cy, sx, sy);
          dots.push({ x: sx, y: sy });
        }
        cy = sy; curAct = seg.activity;
      }

      // Horizontal line across segment
      polyPoints.push(ex, sy);
      cy = sy;

      // Translucent fill for this segment
      const rowIdx = ROW_ORDER.indexOf(seg.activity);
      fills.push({
        activity: seg.activity,
        x: sx, width: ex - sx,
        y: HEADER_H + rowIdx * ROW_H, height: ROW_H,
      });
    });

    // Final dot at the end of the line
    dots.push({ x: polyPoints[polyPoints.length - 2], y: polyPoints[polyPoints.length - 1] });
  }

  return (
    <div>
      {/* SVG graph */}
      <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden", background: "var(--bg3)" }}>
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          width="100%"
          height={SVG_H}
          style={{ display: "block", minWidth: 560 }}
          preserveAspectRatio="none"
        >
          {/* Alternating row backgrounds */}
          {ROW_ORDER.map((_, i) => (
            <rect key={i} x={0} y={HEADER_H + i * ROW_H} width={SVG_W} height={ROW_H}
              fill={i % 2 === 0 ? "rgba(255,255,255,.02)" : "rgba(0,0,0,.08)"} />
          ))}

          {/* Vertical hour grid lines */}
          {HOUR_LABELS.map(({ h }) => (
            <line key={h} x1={slotX(h * 4)} y1={HEADER_H} x2={slotX(h * 4)} y2={SVG_H}
              stroke="rgba(255,255,255,.10)" strokeWidth="1" />
          ))}

          {/* Quarter-hour tick marks (top + bottom of every row) */}
          {Array.from({ length: TOTAL_SLOTS + 1 }, (_, i) => {
            const x = slotX(i);
            const isHour = i % 4 === 0;
            const isHalf = i % 2 === 0;
            const tickH  = isHour ? 8 : isHalf ? 5 : 3;
            return ROW_ORDER.map((_, ri) => {
              const rowTop = HEADER_H + ri * ROW_H;
              return (
                <g key={`${i}-${ri}`}>
                  <line x1={x} y1={rowTop} x2={x} y2={rowTop + tickH}
                    stroke="rgba(255,255,255,.20)" strokeWidth={isHour ? 1 : 0.6} />
                  <line x1={x} y1={rowTop + ROW_H - tickH} x2={x} y2={rowTop + ROW_H}
                    stroke="rgba(255,255,255,.20)" strokeWidth={isHour ? 1 : 0.6} />
                </g>
              );
            });
          })}

          {/* Row separator lines */}
          {ROW_ORDER.map((_, i) => (
            <line key={i} x1={0} y1={HEADER_H + i * ROW_H} x2={SVG_W} y2={HEADER_H + i * ROW_H}
              stroke="var(--border)" strokeWidth="1" />
          ))}
          <line x1={0} y1={SVG_H - 1} x2={SVG_W} y2={SVG_H - 1} stroke="var(--border)" strokeWidth="1" />

          {/* Header + label column borders */}
          <line x1={0} y1={HEADER_H} x2={SVG_W} y2={HEADER_H} stroke="var(--border)" strokeWidth="1" />
          <line x1={LABEL_W} y1={0} x2={LABEL_W} y2={SVG_H} stroke="var(--border)" strokeWidth="1" />

          {/* Hour labels */}
          {HOUR_LABELS.map(({ h, label }) => (
            <text key={h} x={slotX(h * 4)} y={HEADER_H - 5}
              textAnchor="middle" fontSize="8"
              fill={h === 0 || h === 12 || h === 24 ? "rgba(255,255,255,.7)" : "rgba(255,255,255,.4)"}
              fontFamily="JetBrains Mono, monospace">
              {label}
            </text>
          ))}

          {/* Row labels */}
          {ROW_ORDER.map((act, i) => {
            const cy2   = HEADER_H + i * ROW_H + ROW_H / 2;
            const lines = ROW_LABELS[act].split("\n");
            return (
              <text key={act} x={LABEL_W - 6} y={cy2 - (lines.length - 1) * 5}
                textAnchor="end" fontSize="8.5"
                fill="rgba(255,255,255,.5)"
                fontFamily="JetBrains Mono, monospace">
                {lines.map((ln, li) => (
                  <tspan key={li} x={LABEL_W - 6} dy={li === 0 ? 0 : 10}>{ln}</tspan>
                ))}
              </text>
            );
          })}

          {/* Translucent activity fills */}
          {fills.map((f, i) => (
            <rect key={i} x={f.x} y={f.y} width={f.width} height={f.height}
              fill={ROW_COLORS[f.activity]} opacity="0.18" />
          ))}

          {/* Continuous graph line */}
          {polyPoints.length >= 4 && (
            <polyline points={polyPoints.join(" ")}
              fill="none" stroke="#e8eaf0" strokeWidth="2"
              strokeLinejoin="miter" strokeLinecap="square" />
          )}

          {/* Transition dots */}
          {dots.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r={DOT_R}
              fill="#e05252" stroke="#e8eaf0" strokeWidth="1" />
          ))}

          {/* Empty state */}
          {segments.length === 0 && (
            <text x={LABEL_W + GRID_W / 2} y={HEADER_H + (4 * ROW_H) / 2 + 4}
              textAnchor="middle" fontSize="11"
              fill="rgba(255,255,255,.2)"
              fontFamily="JetBrains Mono, monospace">
              No activity logged for this day
            </text>
          )}
        </svg>
      </div>

      {/* Legend */}
      <div className="legend" style={{ marginTop: 10 }}>
        {[["OF","off-duty","Off Duty"],["SB","sleeping","Sleeper Berth"],
          ["D","driving","Driving"],["ON","on-duty","On Duty"]].map(([,color,label]) => (
          <div key={label} className="legend-item">
            <div className="legend-dot" style={{ background: `var(--${color})` }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}