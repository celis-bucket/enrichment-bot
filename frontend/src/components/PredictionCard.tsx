'use client';

import type { OrdersPrediction } from '@/lib/types';

interface PredictionCardProps {
  prediction?: OrdersPrediction | null;
}

const CONFIDENCE_STYLES = {
  high:   { bg: 'bg-green-100', text: 'text-green-800', label: 'High' },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Medium' },
  low:    { bg: 'bg-red-100', text: 'text-red-800', label: 'Low' },
};

function formatOrders(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function PredictionCard({ prediction }: PredictionCardProps) {
  if (!prediction) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Orders Estimation</h3>
        <p className="text-sm text-gray-400">Model could not generate a prediction</p>
      </div>
    );
  }

  const { predicted_orders_p10, predicted_orders_p50, predicted_orders_p90, prediction_confidence } = prediction;
  const conf = CONFIDENCE_STYLES[prediction_confidence] || CONFIDENCE_STYLES.low;

  // Calculate bar positions (log scale for better visualization)
  const maxVal = Math.max(predicted_orders_p90, 1);
  const p10Pct = Math.max(5, (predicted_orders_p10 / maxVal) * 100);
  const p50Pct = Math.max(10, (predicted_orders_p50 / maxVal) * 100);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Orders Estimation</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${conf.bg} ${conf.text}`}>
          {conf.label} confidence
        </span>
      </div>

      {/* Main P50 display */}
      <div className="text-center mb-4">
        <span className="text-3xl font-bold text-gray-900">
          {formatOrders(predicted_orders_p50)}
        </span>
        <p className="text-xs text-gray-500 mt-1">Estimated Monthly Orders</p>
      </div>

      {/* Range bar */}
      <div className="relative mb-2">
        <div className="h-2 bg-gray-100 rounded-full">
          <div
            className="absolute h-2 bg-blue-200 rounded-full"
            style={{ left: `${p10Pct}%`, right: `${100 - 100}%`, width: `${100 - p10Pct}%` }}
          />
          <div
            className="absolute h-2 w-1 bg-blue-600 rounded"
            style={{ left: `${p50Pct}%` }}
          />
        </div>
      </div>

      {/* Range labels */}
      <div className="flex justify-between text-xs text-gray-500">
        <div>
          <span className="font-medium">P10:</span> {formatOrders(predicted_orders_p10)}
        </div>
        <div>
          <span className="font-medium">P50:</span> {formatOrders(predicted_orders_p50)}
        </div>
        <div>
          <span className="font-medium">P90:</span> {formatOrders(predicted_orders_p90)}
        </div>
      </div>
    </div>
  );
}
