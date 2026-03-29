/**
 * SMS sync service — reads bank SMS, parses with transaction-sms-parser,
 * and sends structured transactions to backend.
 * Only works on native Capacitor platform (Android).
 */

import { Capacitor } from "@capacitor/core";
import { getTransactionInfo } from "transaction-sms-parser";

// Bank sender ID patterns
const BANK_SENDER_PATTERNS = [
  "HDFC", "AXIS", "SBI", "KOTAK", "SCAPIA", "ICICI",
  "FED", "BOB", "BARODA", "PNB", "IDFC", "YES", "INDUS",
  "CITI", "HSBC", "STAN", "NIYO", "UNI", "SLICE", "PAYTM",
];

export function isSmsAvailable() {
  return Capacitor.isNativePlatform();
}

/**
 * Read bank SMS, parse locally with transaction-sms-parser, send to backend.
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

    // Filter to bank SMS
    const bankMessages = messages.filter((msg) => {
      const sender = (msg.address || "").toUpperCase();
      return BANK_SENDER_PATTERNS.some((pat) => sender.includes(pat));
    });

    if (bankMessages.length === 0) {
      return { imported: 0, duplicates: 0, messages_processed: 0, balances_extracted: 0, total_sms: messages.length, bank_sms: 0, parsed: 0 };
    }

    // Parse each SMS locally using transaction-sms-parser
    const parsedMessages = [];
    let skipped = 0;

    for (const msg of bankMessages) {
      try {
        const info = getTransactionInfo(msg.body || "");

        // Only proceed if it's an actual transaction (has type and amount)
        if (info?.transaction?.type && info?.transaction?.amount) {
          parsedMessages.push({
            body: msg.body || "",
            sender: msg.address || "",
            date: msg.date ? String(msg.date) : "",
            // Pre-parsed fields from transaction-sms-parser
            parsed: {
              type: info.transaction.type, // "debit" or "credit"
              amount: parseFloat(info.transaction.amount.replace(/,/g, "")),
              merchant: info.transaction.merchant || "",
              reference_id: info.transaction.referenceNo || "",
              account_type: info.account?.type || "", // CARD, ACCOUNT, WALLET
              account_number: info.account?.number || "",
              account_name: info.account?.name || "",
              balance: info.balance?.available ? parseFloat(info.balance.available.replace(/,/g, "")) : null,
            },
          });
        } else {
          skipped++;
        }
      } catch {
        skipped++;
      }
    }

    if (parsedMessages.length === 0) {
      return { imported: 0, duplicates: 0, messages_processed: 0, balances_extracted: 0, total_sms: messages.length, bank_sms: bankMessages.length, parsed: 0, skipped };
    }

    // Send to backend — now with pre-parsed data
    const response = await api.post("/api/sms/sync", { messages: parsedMessages });
    return {
      ...response.data,
      total_sms: messages.length,
      bank_sms: bankMessages.length,
      parsed: parsedMessages.length,
      skipped,
    };
  } catch (error) {
    console.error("SMS sync error:", error);
    return { error: error.message || "SMS sync failed" };
  }
}
