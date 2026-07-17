import { useState, useRef, useEffect } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}

function fmt(d: Date) { return d.toISOString().slice(0, 10); }
function parseDate(s: string) { return new Date(s + "T00:00:00"); }

function addMonths(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(1);
  r.setMonth(r.getMonth() + n);
  return r;
}

const PRESETS: { label: string; get: () => [string, string] }[] = [
  { label: "Heute",              get: () => { const t = fmt(new Date()); return [t, t]; } },
  { label: "Gestern",           get: () => { const d = new Date(); d.setDate(d.getDate()-1); const s=fmt(d); return [s,s]; } },
  { label: "Diese Woche",       get: () => { const d=new Date(); const day=d.getDay()||7; d.setDate(d.getDate()-day+1); return [fmt(d), fmt(new Date())]; } },
  { label: "Letzte Woche",      get: () => { const d=new Date(); const day=d.getDay()||7; d.setDate(d.getDate()-day-6); const e=new Date(d); e.setDate(e.getDate()+6); return [fmt(d),fmt(e)]; } },
  { label: "Diesen Monat",      get: () => { const d=new Date(); return [fmt(new Date(d.getFullYear(),d.getMonth(),1)), fmt(new Date())]; } },
  { label: "Letzten Monat",     get: () => { const d=new Date(); const f=new Date(d.getFullYear(),d.getMonth()-1,1); const t=new Date(d.getFullYear(),d.getMonth(),0); return [fmt(f),fmt(t)]; } },
  { label: "1. Quartal",        get: () => { const y=new Date().getFullYear(); return [`${y}-01-01`,`${y}-03-31`]; } },
  { label: "2. Quartal",        get: () => { const y=new Date().getFullYear(); return [`${y}-04-01`,`${y}-06-30`]; } },
  { label: "3. Quartal",        get: () => { const y=new Date().getFullYear(); return [`${y}-07-01`,`${y}-09-30`]; } },
  { label: "4. Quartal",        get: () => { const y=new Date().getFullYear(); return [`${y}-10-01`,`${y}-12-31`]; } },
  { label: "Dieses Jahr",       get: () => { const y=new Date().getFullYear(); return [`${y}-01-01`,`${y}-12-31`]; } },
  { label: "Letztes Jahr",      get: () => { const y=new Date().getFullYear()-1; return [`${y}-01-01`,`${y}-12-31`]; } },
];

function daysInMonth(year: number, month: number) { return new Date(year, month + 1, 0).getDate(); }
function firstDayOfMonth(year: number, month: number) { return (new Date(year, month, 1).getDay() + 6) % 7; } // 0=Mon

function CalendarMonth({ year, month, from, to, hovered, onDay, onHover }: {
  year: number; month: number;
  from: string | null; to: string | null; hovered: string | null;
  onDay: (d: string) => void; onHover: (d: string) => void;
}) {
  const days = daysInMonth(year, month);
  const firstDay = firstDayOfMonth(year, month);
  const cells: (string | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= days; d++) {
    cells.push(`${year}-${String(month+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`);
  }

  const rangeEnd = hovered ?? to;

  return (
    <div className="flex-1 min-w-[220px]">
      <div className="text-center text-sm font-semibold text-gray-700 mb-2">
        {new Date(year, month).toLocaleDateString("de-DE", { month: "long", year: "numeric" })}
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-xs text-gray-400 mb-1">
        {["Mo","Di","Mi","Do","Fr","Sa","So"].map(d => <div key={d} className="text-center font-medium">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((d, i) => {
          if (!d) return <div key={i} />;
          const isFrom = d === from;
          const isTo = d === to;
          const lo = from && rangeEnd ? (from <= rangeEnd ? from : rangeEnd) : null;
          const hi = from && rangeEnd ? (from <= rangeEnd ? rangeEnd : from) : null;
          const inRange = lo && hi && d > lo && d < hi;
          const isEdge = isFrom || isTo || (lo && d === lo) || (hi && d === hi);
          return (
            <button key={d}
              onClick={() => onDay(d)}
              onMouseEnter={() => onHover(d)}
              className={`text-center py-0.5 text-xs rounded transition-colors
                ${isEdge ? "bg-[#2563eb] text-white font-semibold" :
                  inRange ? "bg-[#2563eb]/15 text-[#2563eb]" :
                  "hover:bg-gray-100 text-gray-700"}`}>
              {parseInt(d.slice(8))}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function DateRangePicker({ from, to, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null); // first click
  const [hovered, setHovered] = useState<string | null>(null);
  const today = new Date();
  const [leftMonth, setLeftMonth] = useState(new Date(today.getFullYear(), today.getMonth() - 1));
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSelecting(null);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleDay(d: string) {
    if (!selecting) {
      setSelecting(d);
    } else {
      const lo = selecting <= d ? selecting : d;
      const hi = selecting <= d ? d : selecting;
      onChange(lo, hi);
      setSelecting(null);
      setOpen(false);
    }
  }

  function handlePreset(get: () => [string, string]) {
    const [f, t] = get();
    onChange(f, t);
    setSelecting(null);
    setOpen(false);
  }

  const rightMonth = addMonths(leftMonth, 1);
  const label = from && to
    ? `${parseDate(from).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric" })} – ${parseDate(to).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric" })}`
    : "Zeitraum wählen";

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white hover:border-[#2563eb] focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30 transition-colors min-w-[220px]">
        <CalendarDays size={14} className="text-[#2563eb] shrink-0" />
        <span className="flex-1 text-left text-gray-700">{label}</span>
      </button>

      {open && (
        <div className="absolute z-50 top-full mt-1 left-0 bg-white border border-gray-200 rounded-xl shadow-xl flex"
          onMouseLeave={() => setHovered(null)}>
          {/* Presets */}
          <div className="border-r border-gray-100 py-3 px-2 flex flex-col gap-0.5 min-w-[150px]">
            {PRESETS.map(p => (
              <button key={p.label} onClick={() => handlePreset(p.get)}
                className="text-left text-sm px-3 py-1 rounded-lg hover:bg-[#2563eb]/10 hover:text-[#2563eb] text-gray-600 transition-colors whitespace-nowrap">
                {p.label}
              </button>
            ))}
          </div>
          {/* Calendars */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-3 gap-4">
              <button onClick={() => setLeftMonth(m => addMonths(m, -1))}
                className="p-1 rounded hover:bg-gray-100"><ChevronLeft size={16} /></button>
              <div className="flex gap-6 flex-1">
                <CalendarMonth year={leftMonth.getFullYear()} month={leftMonth.getMonth()}
                  from={selecting ?? from} to={selecting ? null : to} hovered={selecting ? hovered : null}
                  onDay={handleDay} onHover={setHovered} />
                <CalendarMonth year={rightMonth.getFullYear()} month={rightMonth.getMonth()}
                  from={selecting ?? from} to={selecting ? null : to} hovered={selecting ? hovered : null}
                  onDay={handleDay} onHover={setHovered} />
              </div>
              <button onClick={() => setLeftMonth(m => addMonths(m, 1))}
                className="p-1 rounded hover:bg-gray-100"><ChevronRight size={16} /></button>
            </div>
            {selecting && (
              <div className="text-xs text-center text-gray-400 mt-1">
                Enddatum wählen… <button onClick={() => setSelecting(null)} className="text-red-400 hover:underline ml-1">Abbrechen</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
