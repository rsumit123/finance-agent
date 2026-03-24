import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Attach auth token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Expenses
export const getExpenses = (params = {}) => {
  const p = { ...params };
  // Convert start_date/end_date to the format the API expects
  if (p.start_date && p.end_date && !p.period) {
    delete p.period;
  }
  return api.get("/api/expenses/", { params: p }).then((r) => r.data);
};

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

export const getInsights = ({ start_date, end_date } = {}) => {
  const params = {};
  if (start_date && end_date) { params.start_date = start_date; params.end_date = end_date; }
  return api.get("/api/expenses/insights", { params }).then((r) => r.data);
};

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

export const startGmailSync = ({ full = false, after = "", before = "", jobType = "all" } = {}) => {
  const params = { job_type: jobType };
  if (full) params.full = true;
  if (after) params.after = after;
  if (before) params.before = before;
  return api.post("/api/gmail/sync", null, { params }).then((r) => r.data);
};

export const getSyncStatus = (jobId) =>
  api.get(`/api/gmail/sync/${jobId}`).then((r) => r.data);

export const getLatestSync = () =>
  api.get("/api/gmail/sync/latest").then((r) => r.data);

export const disconnectGmail = () =>
  api.post("/api/gmail/disconnect").then((r) => r.data);

// Settings
export const getPasswords = () =>
  api.get("/api/settings/passwords").then((r) => r.data);

export const addPassword = (label, password) =>
  api.post("/api/settings/passwords", { label, password }).then((r) => r.data);

export const deletePassword = (id) =>
  api.delete(`/api/settings/passwords/${id}`).then((r) => r.data);

export const clearAllData = () =>
  api.post("/api/settings/clear-data").then((r) => r.data);

export const recategorize = (userName = "") =>
  api.post("/api/settings/recategorize", null, { params: { user_name: userName } }).then((r) => r.data);
