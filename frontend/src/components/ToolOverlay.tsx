import { ReactNode } from 'react';

type Props = {
  title: string;
  onClose: () => void;
  onOpenWindow?: () => void;
  children: ReactNode;
};

/** Keep the current page (patient chart, pharmacy, etc.) while using a tool. */
export default function ToolOverlay({ title, onClose, onOpenWindow, children }: Props) {
  return (
    <div className="tool-overlay-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="tool-overlay-panel" onClick={e => e.stopPropagation()}>
        <div className="tool-overlay-header">
          <h5 className="mb-0">{title}</h5>
          <div className="d-flex gap-2">
            {onOpenWindow && (
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onOpenWindow} title="Open in new window">
                <i className="fas fa-external-link-alt me-1"></i>New window
              </button>
            )}
            <button type="button" className="btn btn-sm btn-light" onClick={onClose} aria-label="Close">
              <i className="fas fa-times"></i>
            </button>
          </div>
        </div>
        <div className="tool-overlay-body">{children}</div>
      </div>
    </div>
  );
}
