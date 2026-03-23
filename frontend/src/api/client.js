import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Expenses
export const getExpenses = (params = {}) =>
  api.get("/api/expenses/", { params }).then((r) => r.data);

export const addExpense = (data) =>
  api.post("/api/expenses/", data).then((r) => r.data);

export const updateExpense = (id, updates) =>
  api.patch(`/api/expenses/${id}`, updates).then((r) => r.data);

export const deleteExpense = (id) =>
  api.delete(`/api/expenses/${id}`).then((r) => r.data);

export const getExpenseSummary = ({ period, start_date, end_date } = {}) => {
  const params = {};
  if (start_date && end_date) {
    params.start_date = start_date;
    params.end_date = end_date;
  } else {
    params.period = period || "month";
  }
  return api.get("/api/expenses/summary", { params }).then((r) => r.data);
};

export const getSubscriptions = () =>
  api.get("/api/expenses/subscriptions").then((r) => r.data);

export const getSources = () =>
  api.get("/api/expenses/sources").then((r) => r.data);

export const getNetworth = ({ period, start_date, end_date } = {}) => {
  const params = {};
  if (start_date && end_date) {
    params.start_date = start_date;
    params.end_date = end_date;
  } else if (period) {
    params.period = period;
  }
  return api.get("/api/expenses/networth", { params }).then((r) => r.data);
};

// Budget
export const getBudget = () =>
  api.get("/api/budget/").then((r) => r.data);

export const setBudget = (data) =>
  api.post("/api/budget/", data).then((r) => r.data);

export const getBudgetStatus = () =>
  api.get("/api/budget/status").then((r) => r.data);

// Upload
export const uploadStatement = (file, fileType = "auto", password = "") => {
  const form = new FormData();
  form.append("file", file);
  const params = { file_type: fileType };
  if (password) params.password = password;
  return api
    .post("/api/upload/", form, { params })
    .then((r) => r.data);
};

export const getUploadHistory = () =>
  api.get("/api/upload/history").then((r) => r.data);

// Advisor
export const canIBuy = (amount, category = null) =>
  api
    .post("/api/advisor/can-i-buy", { amount, category })
    .then((r) => r.data);

// Gmail
export const getGmailStatus = () =>
  api.get("/api/gmail/status").then((r) => r.data);

export const getGmailAuthUrl = () =>
  api.get("/api/gmail/auth").then((r) => r.data);

export const startGmailSync = ({ full = false, after = "", before = "" } = {}) => {
  const params = {};
  if (full) params.full = true;
  if (after) params.after = after;
  if (before) params.before = before;
  return api.post("/api/gmail/sync", null, { params }).then((r) => r.data);
};

export const disconnectGmail = () =>
  api.post("/api/gmail/disconnect").then((r) => r.data);

export const syncStatements = () =>
  api.post("/api/gmail/sync-statements").then((r) => r.data);

// Settings
export const getPasswords = () =>
  api.get("/api/settings/passwords").then((r) => r.data);

export const addPassword = (label, password) =>
  api.post("/api/settings/passwords", { label, password }).then((r) => r.data);

export const deletePassword = (id) =>
  api.delete(`/api/settings/passwords/${id}`).then((r) => r.data);

export const clearAllData = () =>
  api.post("/api/settings/clear-data").then((r) => r.data);
