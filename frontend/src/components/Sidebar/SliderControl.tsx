interface Props {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}

export default function SliderControl({
  label,
  value,
  min,
  max,
  onChange,
}: Props) {
  return (
    <div className="px-4 py-3">
      <label className="text-sm font-semibold text-gray-800 block mb-2">
        {label}
      </label>
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 w-6 text-right font-mono tabular-nums">
          {String(min).padStart(2, "0")}
        </span>
        <input
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 h-1 accent-indigo-500 cursor-pointer"
        />
        <span className="text-xs text-gray-400 w-6 font-mono tabular-nums">
          {max}
        </span>
      </div>
    </div>
  );
}
