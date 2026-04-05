/**
 * SMS sync service — reads bank SMS from device and sends raw messages
 * to backend for LLM-powered parsing.
 * Only works on native Capacitor platform (Android).
 */

import { Capacitor } from "@capacitor/core";

// Bank sender ID patterns (TRAI suffix is primary, these are fallback)
const BANK_SENDER_PATTERNS = [
  "HDFC", "AXIS", "SBI", "KOTAK", "SCAPIA", "ICICI",
  "FED", "FEDBK", "FEDBNK", "SCPFED", "FEDSCP",
  "BOB", "BARODA", "PNB", "IDFC", "YES", "INDUS",
  "CITI", "HSBC", "STAN", "NIYO", "UNI", "SLICE", "PAYTM",
  "CANBNK", "IOB", "BOBIBN", "UNIONB", "KBLBNK",
];

export function isSmsAvailable() {
  return Capacitor.isNativePlatform();
}

/**
 * Read bank SMS and send raw messages to backend for parsing.
 * Backend uses LLM (Gemini Flash) with regex fallback.
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

    const afterDate = new Date();
    afterDate.setDate(afterDate.getDate() - daysBack);

    // Read SMS
    const result = await SMSInboxReader.getSMSList({
      filter: { type: 1, minDate: afterDate.getTime(), maxCount: 1000 },
      projection: { id: true, address: true, body: true, date: true },
    });

    const messages = result.smsList || [];

    // Filter to potential bank SMS using two strategies:
    // 1. TRAI suffix: sender ends with -T (transactional) or -S (service)
    // 2. Known bank sender ID patterns as fallback
    const bankMessages = messages.filter((msg) => {
      const sender = (msg.address || "").toUpperCase();
      if (sender.endsWith("-T") || sender.endsWith("-S")) return true;
      return BANK_SENDER_PATTERNS.some((pat) => sender.includes(pat));
    });

    if (bankMessages.length === 0) {
      return { imported: 0, duplicates: 0, messages_processed: 0, balances_extracted: 0, total_sms: messages.length, bank_sms: 0 };
    }

    // Send raw SMS to backend — LLM parses on server side
    const rawMessages = bankMessages.map((msg) => ({
      body: msg.body || "",
      sender: msg.address || "",
      date: msg.date ? String(msg.date) : "",
    }));

    const response = await api.post("/api/sms/sync", { messages: rawMessages });
    return {
      ...response.data,
      total_sms: messages.length,
      bank_sms: bankMessages.length,
    };
  } catch (error) {
    console.error("SMS sync error:", error);
    return { error: error.message || "SMS sync failed" };
  }
}
