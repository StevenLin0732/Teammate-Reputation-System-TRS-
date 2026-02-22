'use client';

import { useEffect, useState } from 'react';
import { X } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export interface Alert {
  id: string;
  category: 'success' | 'danger' | 'warning' | 'info' | 'secondary';
  message: string;
}

interface AlertProps {
  alert: Alert;
  onDismiss: (id: string) => void;
}

export function Alert({ alert, onDismiss }: AlertProps) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onDismiss(alert.id), 300);
    }, 5000);

    return () => clearTimeout(timer);
  }, [alert.id, onDismiss]);

  const variants = {
    success: 'bg-green-50 border-green-200 text-green-800',
    danger: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    secondary: 'bg-gray-50 border-gray-200 text-gray-800',
  };

  if (!isVisible) return null;

  return (
    <div
      className={cn(
        'border rounded-lg p-4 flex items-center justify-between gap-4 transition-opacity',
        variants[alert.category]
      )}
    >
      <span>{alert.message}</span>
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onDismiss(alert.id), 300);
        }}
        className="flex-shrink-0"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

interface AlertContainerProps {
  alerts: Alert[];
  onDismiss: (id: string) => void;
}

export function AlertContainer({ alerts, onDismiss }: AlertContainerProps) {
  if (alerts.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      {alerts.map((alert) => (
        <Alert key={alert.id} alert={alert} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
