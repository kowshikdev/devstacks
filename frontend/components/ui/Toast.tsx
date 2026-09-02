"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { IconButton } from "./Button";
import { XIcon } from "./Icon";

export type ToastTone = "neutral" | "success" | "danger" | "info";

interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastApi {
  toast: (input: { title: string; description?: string; tone?: ToastTone }) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const DISMISS_AFTER_MS = 5200;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((item) => item.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback<ToastApi["toast"]>(
    ({ title, description, tone = "neutral" }) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-3), { id, title, description, tone }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), DISMISS_AFTER_MS)
      );
    },
    [dismiss]
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach((timer) => clearTimeout(timer));
      pending.clear();
    };
  }, []);

  const api = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" role="region" aria-label="Notifications">
        {toasts.map((item) => (
          <output
            key={item.id}
            className={["toast", item.tone !== "neutral" ? `toast--${item.tone}` : ""]
              .filter(Boolean)
              .join(" ")}
          >
            <div className="toast__body">
              <p className="toast__title">{item.title}</p>
              {item.description ? <p className="toast__description">{item.description}</p> : null}
            </div>
            <IconButton
              icon={<XIcon size={14} />}
              label="Dismiss notification"
              onClick={() => dismiss(item.id)}
            />
          </output>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * Returns a no-op outside a provider so a component can announce results
 * without every tree being forced to mount the toast region.
 */
export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  return context ?? { toast: () => undefined };
}
