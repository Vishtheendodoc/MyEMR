import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { api } from '../api/client';
import { recallTyped, rememberTyped } from '../utils/typedMemory';

type Props = {
  field: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  rows?: number;
  className?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  id?: string;
};

type Hit = { value: string; source: string };

export default function SuggestField({
  field,
  value,
  onChange,
  multiline = false,
  rows = 2,
  className = 'form-control',
  placeholder,
  required,
  disabled,
  id,
}: Props) {
  const autoId = useId();
  const inputId = id || autoId;
  const [open, setOpen] = useState(false);
  const [hits, setHits] = useState<Hit[]>([]);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const skipBlurClose = useRef(false);

  const localHits = useMemo(
    () => recallTyped(field, value).map(v => ({ value: v, source: 'recent' as const })),
    [field, value],
  );

  useEffect(() => {
    if (!open) return;
    const q = value.trim();
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api.fieldSuggestions(field, q)
        .then(rows => {
          if (cancelled) return;
          const merged: Hit[] = [];
          const seen = new Set<string>();
          [...localHits, ...rows].forEach(row => {
            const key = row.value.toLowerCase();
            if (seen.has(key) || row.value.trim() === value.trim()) return;
            seen.add(key);
            merged.push(row);
          });
          setHits(merged.slice(0, 12));
          setActive(0);
        })
        .catch(() => {
          if (!cancelled) {
            setHits(localHits.filter(h => h.value.trim() !== value.trim()).slice(0, 12));
            setActive(0);
          }
        });
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [field, value, open, localHits]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const pick = (text: string) => {
    onChange(text);
    rememberTyped(field, text);
    setOpen(false);
  };

  const commitMemory = () => {
    rememberTyped(field, value);
  };

  const onKeyDown = (e: ReactKeyboardEvent) => {
    if (!open || hits.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive(i => (i + 1) % hits.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(i => (i - 1 + hits.length) % hits.length);
    } else if (e.key === 'Enter' && !multiline) {
      e.preventDefault();
      pick(hits[active].value);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const shared = {
    id: inputId,
    className,
    value,
    required,
    disabled,
    placeholder,
    autoComplete: 'off',
    onFocus: () => setOpen(true),
    onBlur: () => {
      window.setTimeout(() => {
        if (!skipBlurClose.current) {
          commitMemory();
          setOpen(false);
        }
        skipBlurClose.current = false;
      }, 120);
    },
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      onChange(e.target.value);
      setOpen(true);
    },
    onKeyDown,
  };

  return (
    <div className="suggest-field" ref={wrapRef}>
      {multiline ? (
        <textarea {...shared} rows={rows} />
      ) : (
        <input type="text" {...shared} />
      )}
      {open && hits.length > 0 && (
        <div className="suggest-menu list-group shadow-sm" role="listbox">
          {hits.map((hit, index) => (
            <button
              type="button"
              key={`${hit.source}-${hit.value}`}
              className={`list-group-item list-group-item-action suggest-item${index === active ? ' active' : ''}`}
              onMouseDown={() => { skipBlurClose.current = true; }}
              onClick={() => pick(hit.value)}
            >
              <span>{hit.value}</span>
              <small className="text-muted ms-2">{hit.source === 'recent' ? 'recent' : hit.source === 'master' ? 'list' : 'clinic'}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
