import { useState } from 'react';
import { api } from '../api/client';

export function LockedDayNotice({
  message,
  day,
  canOpen,
  className = 'alert alert-danger',
  onOpened,
}: {
  message: string;
  day?: string;
  canOpen: boolean;
  className?: string;
  onOpened: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState('');
  const show = canOpen && !!day && message.toLowerCase().includes('locked');

  return (
    <div className={className}>
      {message}
      {localError && <div className="small mt-1">{localError}</div>}
      {show && (
        <div className="mt-2">
          <button
            type="button"
            className="btn btn-sm btn-outline-danger"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setLocalError('');
              try {
                await api.reopenDayClose({ day });
                onOpened();
              } catch (err) {
                setLocalError(err instanceof Error ? err.message : 'Failed to open day');
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? 'Opening…' : 'Open this day'}
          </button>
        </div>
      )}
    </div>
  );
}
