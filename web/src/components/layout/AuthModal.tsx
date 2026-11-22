import { LockKeyhole, X } from "lucide-react";

export default function AuthModal({ open, onClose, onAdmin }: { open: boolean; onClose: () => void; onAdmin: () => void }) {
  if (!open) return null;
  return <div className="modal-backdrop"><div className="auth-modal"><button className="modal-close" onClick={onClose}><X size={18} /></button><div className="auth-icon"><LockKeyhole size={22} /></div><span className="eyebrow">Admin access</span><h2>Unlock your lead engine.</h2><p>This portfolio preview is read-only. Switch to the demo admin workspace to launch scrapes and update outreach records.</p><button className="dispatch-button" onClick={onAdmin}>Enter demo admin mode</button><button className="text-button" onClick={onClose}>Continue exploring</button></div></div>;
}
