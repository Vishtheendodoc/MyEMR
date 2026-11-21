import { useEffect, useMemo, useRef, useState } from 'react';

export type PriceSuggestion = {
  label: string;
  detail?: string;
  code?: string;
  rate?: string;
  gst?: string;
};

type Props = {
  value: string;
  items: PriceSuggestion[];
  placeholder?: string;
  onChange: (value: string) => void;
  onPick: (item: PriceSuggestion) => void;
};

export default function PriceSuggest({ value, items, placeholder, onChange, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const query = value.trim().toLowerCase();
  const matches = useMemo(() => {
    const rows = query
      ? items.filter(item => item.label.toLowerCase().includes(query))
      : items;
    return rows.slice(0, 8);
  }, [items, query]);

  useEffect(() => {
    setActive(0);
  }, [query, open]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, []);

  const choose = (item: PriceSuggestion) => {
    onPick(item);
    setOpen(false);
  };

  return (
    <div className="position-relative" ref={wrapRef}>
      <input
        className="form-control"
        placeholder={placeholder}
        value={value}
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onChange={e => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onKeyDown={e => {
          if (!open || matches.length === 0) return;
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive(index => (index + 1) % matches.length);
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive(index => (index - 1 + matches.length) % matches.length);
          } else if (e.key === 'Enter' && matches[active]) {
            e.preventDefault();
            choose(matches[active]);
          } else if (e.key === 'Escape') {
            setOpen(false);
          }
        }}
      />
      {open && matches.length > 0 && (
        <div className="list-group position-absolute w-100 shadow-sm mt-1" style={{ zIndex: 30, maxHeight: 220, overflow: 'auto' }}>
          {matches.map((item, index) => (
            <button
              type="button"
              key={`${item.label}-${index}`}
              className={`list-group-item list-group-item-action py-2 ${index === active ? 'active' : ''}`}
              onMouseDown={e => e.preventDefault()}
              onClick={() => choose(item)}
            >
              <div className="d-flex justify-content-between gap-2">
                <span className="fw-semibold">{item.label}</span>
                {item.rate ? <span>₹{item.rate}</span> : null}
              </div>
              {item.detail && <div className="small text-muted">{item.detail}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
