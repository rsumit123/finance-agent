/**
 * SMS sync service — reads bank SMS from device inbox and sends to backend.
 * Only works on native Capacitor platform (Android).
 */

import { Capacitor } from "@capacitor/core";

// Bank sender IDs used by Indian banks in SMS
const BANK_SENDERS = [
  "HDFCBK", "HDFC", "HDFCBANK",
  "AXISBK", "AXIS", "AXISBNK",
  "SBIBNK", "SBIETX", "SBIINB", "ATMSBI",
  "KOTAKB", "KOTAK", "KOTAKM",
  "SCAPIA", "FEDBK", "FEDBNK",
  "ICICIB", "ICICI",
  "BOBTXN", "BARODA",
  "PNBSMS",
  "IDFCFB",
  "YESBK",
  "IDBIBK",
];

/**
 * Check if SMS sync is available (native platform only)
 */
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
    // Dynamic import — only loads on native
    const { SmsInbox } = await import("capacitor-sms-inbox");

    // Request permission
    const permResult = await SmsInbox.checkPermission();
    if (permResult.granted !== true) {
      const reqResult = await SmsInbox.requestPermission();
      if (reqResult.granted !== true) {
        return { error: "SMS permission denied" };
      }
    }

    // Calculate date filter
    const afterDate = new Date();
    afterDate.setDate(afterDate.getDate() - daysBack);

    // Read SMS messages
    const result = await SmsInbox.getMessages({
      maxCount: 500,
      afterDate: afterDate.getTime(),
    });

    const messages = result.messages || [];

    // Filter to bank SMS only
    const bankMessages = messages.filter((msg) => {
      const sender = (msg.address || msg.sender || "").toUpperCase();
      return BANK_SENDERS.some((bs) => sender.includes(bs));
    });

    if (bankMessages.length === 0) {
      return { imported: 0, duplicates: 0, messages_processed: 0, balances_extracted: 0 };
    }

    // Send to backend for parsing
    const payload = bankMessages.map((msg) => ({
      body: msg.body || "",
      sender: msg.address || msg.sender || "",
      date: msg.date ? String(msg.date) : "",
    }));

    const response = await api.post("/api/sms/sync", { messages: payload });
    return response.data;
  } catch (error) {
    console.error("SMS sync error:", error);
    return { error: error.message || "SMS sync failed" };
  }
}
