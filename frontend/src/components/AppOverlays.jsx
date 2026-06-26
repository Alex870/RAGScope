import React from "react";

import { short } from "../lib/helpers";

export function AppOverlays({ controller }) {
  return (
    <>
      {controller.messageModal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => controller.setMessageModal(null)}>
          <div className="message-modal" role="dialog" aria-modal="true" aria-label={controller.messageModal.title} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{controller.messageModal.title}</h2>
              <div className="button-row">
                <button type="button" className="icon-button" title="Copy message to clipboard" onClick={controller.copyModalText}>⧉</button>
                <button type="button" className="icon-button" title="Close" onClick={() => controller.setMessageModal(null)}>×</button>
              </div>
            </div>
            <pre>{controller.messageModal.text}</pre>
          </div>
        </div>
      )}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {controller.toasts.map((toast) => (
          <div className={`toast ${toast.type}`} key={toast.id}>
            <div>
              <strong>{toast.title}</strong>
              <button type="button" onClick={() => controller.setMessageModal({ title: toast.title, text: toast.message })}>
                {short(toast.message, 180)}
              </button>
            </div>
            <button type="button" className="toast-dismiss" title="Dismiss notification" onClick={() => controller.dismissToast(toast.id)}>×</button>
          </div>
        ))}
      </div>
    </>
  );
}
