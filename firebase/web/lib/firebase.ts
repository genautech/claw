/**
 * Firebase Client SDK Configuration
 * Project: openslaver
 */

import { initializeApp, getApps, getApp } from 'firebase/app'
import { getFirestore } from 'firebase/firestore'
import { getAnalytics, isSupported } from 'firebase/analytics'

const firebaseConfig = {
  apiKey: "AIzaSyCkiVPliPHoxwnIi7mA-yMDlMzXgtC1x9c",
  authDomain: "openslaver.firebaseapp.com",
  projectId: "openslaver",
  storageBucket: "openslaver.firebasestorage.app",
  messagingSenderId: "376161033221",
  appId: "1:376161033221:web:d648c15b3c914f6af8d06c",
  measurementId: "G-R3GG7M7WLD",
}

// Initialize Firebase (singleton)
const app = getApps().length ? getApp() : initializeApp(firebaseConfig)

// Firestore instance
export const db = getFirestore(app)

// Analytics (only in browser, not during SSR/build)
export const analytics = typeof window !== 'undefined'
  ? isSupported().then((ok) => (ok ? getAnalytics(app) : null))
  : null

export default app
