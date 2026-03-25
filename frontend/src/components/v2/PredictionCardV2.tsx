'use client';

import { useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import type { OrdersPrediction, FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface PredictionCardV2Props {
  prediction?: OrdersPrediction | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

function formatOrders(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function PredictionCardV2({ prediction, domain = '', feedback = [] }: PredictionCardV2Props) {
  const confettiFired = useRef(false);

  useEffect(() => {
    if (prediction && prediction.predicted_orders_p50 >= 500 && !confettiFired.current) {
      confettiFired.current = true;
      // Fire confetti with Melonn brand colors
      confetti({
        particleCount: 150,
        spread: 80,
        origin: { y: 0.6 },
        colors: ['#4929A1', '#00C97A', '#74EBAE', '#FF802F', '#75E7EA'],
      });
      // Second burst for extra celebration
      setTimeout(() => {
        confetti({
          particleCount: 80,
          spread: 60,
          origin: { y: 0.5, x: 0.3 },
          colors: ['#4929A1', '#00C97A', '#74EBAE'],
        });
        confetti({
          particleCount: 80,
          spread: 60,
          origin: { y: 0.5, x: 0.7 },
          colors: ['#FF802F', '#75E7EA', '#4929A1'],
        });
      }, 300);
    }
  }, [prediction]);

  if (!prediction) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Órdenes Estimadas</h3>
        <p className="text-sm text-melonn-navy/40">No se pudo generar una predicción</p>
        {domain && <FeedbackPanel domain={domain} section="prediction" existingFeedback={feedback} />}
      </div>
    );
  }

  const { predicted_orders_p10, predicted_orders_p50, predicted_orders_p90 } = prediction;
  const isIdeal = predicted_orders_p50 >= 500;

  // Calculate bar positions
  const maxVal = Math.max(predicted_orders_p90, 1);
  const p10Pct = Math.max(5, (predicted_orders_p10 / maxVal) * 100);
  const p50Pct = Math.max(10, (predicted_orders_p50 / maxVal) * 100);

  return (
    <div className={`rounded-2xl border shadow-sm p-5 ${
      isIdeal
        ? 'bg-gradient-to-br from-melonn-green-50 to-white border-melonn-green'
        : 'bg-white border-melonn-purple-50'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Órdenes Estimadas</h3>
      </div>

      {/* Celebration banner for 500+ orders */}
      {isIdeal && (
        <div className="bg-melonn-green text-white rounded-xl px-4 py-3 mb-4 text-center">
          <p className="text-lg font-bold font-heading">🎉 Esta marca es ideal para Melonn!</p>
          <p className="text-sm opacity-90 mt-0.5">Más de 500 órdenes mensuales estimadas</p>
        </div>
      )}

      {/* Main P50 display */}
      <div className="text-center mb-4">
        <span className="text-3xl font-bold text-melonn-navy font-heading">
          {formatOrders(predicted_orders_p50)}
        </span>
        <p className="text-xs text-melonn-navy/50 mt-1">Órdenes mensuales estimadas</p>
      </div>

      {/* Range bar */}
      <div className="relative mb-2">
        <div className="h-2 bg-melonn-purple-100 rounded-full">
          <div
            className="absolute h-2 bg-melonn-purple-50 rounded-full"
            style={{ left: `${p10Pct}%`, width: `${100 - p10Pct}%` }}
          />
          <div
            className="absolute h-2 w-1 bg-melonn-purple rounded"
            style={{ left: `${p50Pct}%` }}
          />
        </div>
      </div>

      {/* Range labels - friendly names */}
      <div className="flex justify-between text-xs text-melonn-navy/50">
        <div>
          <span className="font-medium">Pesimista:</span> {formatOrders(predicted_orders_p10)}
        </div>
        <div>
          <span className="font-medium">Conservador:</span> {formatOrders(predicted_orders_p50)}
        </div>
        <div>
          <span className="font-medium">Optimista:</span> {formatOrders(predicted_orders_p90)}
        </div>
      </div>

      {domain && <FeedbackPanel domain={domain} section="prediction" existingFeedback={feedback} />}
    </div>
  );
}
