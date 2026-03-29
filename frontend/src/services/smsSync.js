/**
 * SMS sync service — reads bank SMS from device inbox and sends to backend.
 * Only works on native Capacitor platform (Android).
 */

import { Capacitor } from "@capacitor/core";

// Bank sender IDs used by Indian banks in SMS
const BANK_SENDER_PATTERNS = [
  "HDFC", "AXIS", "SBI", "KOTAK", "SCAPIA", "ICICI",
  "FED", "BOB", "BARODA", "PNB", "IDFC", "YES", "INDUS",
];

export function isSmsAvailable() {
  return Capacitor.isNativePlatform();
}

/**
 * Read bank SMS from device inbox and sync with backend.
 * @param {object} api - axios API instance
 * @param {number} daysBack - how many days of SMS to read (default 90)
 * @returns {object|null} sync result or null if not available
 */
export async function syncSmsMessages(api, daysBack = 90) {
  if (!Capacitor.isNativePlatform()) return null;

  try {
    const { SMSInboxReader } = await import("capacitor-sms-inbox");

    // Request permission
    const permStatus = await SMSInboxReader.checkPermissions();
    if (permStatus.sms !== "granted") {
      const reqResult = await SMSInboxReader.requestPermissions();
      if (reqResult.sms !== "granted") {
        return { error: "SMS permission denied. Please grant SMS access in Settings." };
      }
    }

    // Calculate date filter
    const afterDate = new Date();
    afterDate.setDate(afterDate.getDate() - daysBack);

    // Read SMS messages from inbox
    const result = await SMSInboxReader.getSMSList({
      filter: {
        type: 1, // INBOX
        minDate: afterDate.getTime(),
        maxCount: 1000,
      },
      projection: {
        id: true,
        address: true,
        body: true,
        date: true,
      },
    });

    const messages = result.smsList || [];

    // Filter to bank SMS only
    const bankMessages = messages.filter((msg) => {
      const sender = (msg.address || "").toUpperCase();
      return BANK_SENDER_PATTERNS.some((pat) => sender.includes(pat));
    });

    if (bankMessages.length === 0) {
      return { imported: 0, duplicates: 0, messages_processed: 0, balances_extracted: 0, skipped: 0, total_sms: messages.length };
    }

    // Send to backend for parsing
    const payload = bankMessages.map((msg) => ({
      body: msg.body || "",
      sender: msg.address || "",
      date: msg.date ? String(msg.date) : "",
    }));

    const response = await api.post("/api/sms/sync", { messages: payload });
    return { ...response.data, total_sms: messages.length, bank_sms: bankMessages.length };
  } catch (error) {
    console.error("SMS sync error:", error);
    return { error: error.message || "SMS sync failed" };
  }
}
