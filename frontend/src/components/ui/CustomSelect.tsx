import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export interface SelectOption<T = string | number> {
  value: T;
  label: string;
}

interface CustomSelectProps<T = string | number> {
  options: SelectOption<T>[];
  value: T;
  onChange: (value: T) => void;
  placeholder?: string;
  className?: string;
  dropDirection?: "up" | "down";
}

export function CustomSelect<T = string | number>({
  options,
  value,
  onChange,
  placeholder = "Select an option",
  className = "",
  dropDirection = "down",
}: CustomSelectProps<T>) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const menuPlacementClass =
    dropDirection === "up"
      ? "bottom-[calc(100%+6px)] mb-0"
      : "top-[calc(100%+6px)] mt-0";

  return (
    <div
      ref={containerRef}
      className={`relative select-none ${open ? "z-50" : "z-10"} ${className}`}
    >
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex h-[42px] w-full items-center justify-between rounded-[10px] border px-3.5 text-sm text-foreground transition-all duration-200 outline-none cursor-pointer ${
          open
            ? "border-white/50 bg-black/75 shadow-[0_0_0_1px_rgba(255,255,255,0.2)]"
            : "border-white/15 bg-black/45 hover:border-white/30 hover:bg-black/60"
        }`}
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <ChevronDown
          className={`size-4 text-muted-foreground transition-transform duration-200 shrink-0 ml-2 ${
            open ? "rotate-180 text-foreground" : ""
          }`}
        />
      </button>

      {/* Floating Glassmorphic Dropdown Menu */}
      {open && (
        <div
          className={`absolute left-0 ${menuPlacementClass} z-50 max-h-60 w-full overflow-y-auto rounded-xl border border-white/20 bg-[#071322] p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.9)] backdrop-blur-3xl`}
        >
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <div
                key={String(opt.value)}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                  isSelected
                    ? "bg-white/15 font-medium text-white shadow-sm"
                    : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && <Check className="size-4 text-white shrink-0 ml-2" />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
