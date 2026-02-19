/**
 * Firestore Direct Client
 * Reads data directly from Firestore (no backend needed for public collections).
 * Writes still go through the Cloud Run API for auth/validation.
 */

import { db } from './firebase'
import {
  collection,
  doc,
  getDoc,
  getDocs,
  query,
  orderBy,
  limit as firestoreLimit,
  where,
} from 'firebase/firestore'

import type { Config, Prediction, Trade, Metric } from './api'

// ── Config ──────────────────────────────────────────────

export async function getConfigDirect(): Promise<Config | null> {
  const snap = await getDoc(doc(db, 'config', 'main'))
  return snap.exists() ? (snap.data() as Config) : null
}

// ── Predictions ─────────────────────────────────────────

export async function getPredictionsDirect(
  marketId?: string,
  max = 50
): Promise<(Prediction & { id: string })[]> {
  let q = query(
    collection(db, 'predictions'),
    orderBy('timestamp', 'desc'),
    firestoreLimit(max)
  )
  if (marketId) {
    q = query(q, where('market_id', '==', marketId))
  }
  const snap = await getDocs(q)
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Prediction & { id: string }))
}

// ── Trades ──────────────────────────────────────────────

export async function getTradesDirect(
  status?: string,
  max = 50
): Promise<(Trade & { id: string })[]> {
  let q = query(
    collection(db, 'trades'),
    orderBy('timestamp', 'desc'),
    firestoreLimit(max)
  )
  if (status) {
    q = query(q, where('status', '==', status))
  }
  const snap = await getDocs(q)
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Trade & { id: string }))
}

// ── Metrics ─────────────────────────────────────────────

export async function getMetricsDirect(
  metricType?: string,
  max = 100
): Promise<(Metric & { id: string })[]> {
  let q = query(
    collection(db, 'metrics'),
    orderBy('timestamp', 'desc'),
    firestoreLimit(max)
  )
  if (metricType) {
    q = query(q, where('type', '==', metricType))
  }
  const snap = await getDocs(q)
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Metric & { id: string }))
}
