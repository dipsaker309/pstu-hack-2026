const state = {
  token: localStorage.getItem("moneyMovementToken"),
  user: null,
  page: "balance",
};

const authPanel = document.querySelector("#authPanel");
const appPanel = document.querySelector("#appPanel");
const toast = document.querySelector("#toast");
const welcomeText = document.querySelector("#welcomeText");
const balanceText = document.querySelector("#balanceText");
const summaryUser = document.querySelector("#summaryUser");
const summaryEmail = document.querySelector("#summaryEmail");
const requestsList = document.querySelector("#requestsList");
const transactionsList = document.querySelector("#transactionsList");
const showLogin = document.querySelector("#showLogin");
const showRegister = document.querySelector("#showRegister");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const sendOtpButton = document.querySelector("#sendOtpButton");
const navButtons = document.querySelectorAll("[data-page]");
const pagePanels = document.querySelectorAll("[data-page-panel]");

showLogin.addEventListener("click", () => setAuthMode("login"));
showRegister.addEventListener("click", () => setAuthMode("register"));

document.querySelectorAll(".demo-account").forEach((button) => {
  button.addEventListener("click", () => {
    setAuthMode("login");
    loginForm.elements.username_or_email.value = button.dataset.username;
    loginForm.elements.password.value = button.dataset.password;
    loginForm.elements.password.focus();
  });
});

sendOtpButton.addEventListener("click", async () => {
  const email = registerForm.elements.email.value.trim();

  if (!email) {
    showToast("Please enter your email first");
    registerForm.elements.email.focus();
    return;
  }

  try {
    await api("/api/auth/send-otp", {
      method: "POST",
      body: { email },
      publicRequest: true,
    });
    showToast("OTP sent to your email");
    registerForm.elements.otp.focus();
  } catch (error) {
    showToast(error.message || "Unable to send OTP");
  }
});

navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setDashboardPage(button.dataset.page);
  });
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const otp = String(form.get("otp") || "").trim();

  if (!/^\d{4}$/.test(otp)) {
    showToast("Please enter a valid 4-digit OTP");
    return;
  }

  await authenticate("/api/auth/register", {
    username: form.get("username"),
    email: form.get("email"),
    password: form.get("password"),
    otp,
  });
  event.currentTarget.reset();
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await authenticate("/api/auth/login", {
    username_or_email: form.get("username_or_email"),
    password: form.get("password"),
  });
  event.currentTarget.reset();
});

document.querySelector("#logoutButton").addEventListener("click", () => {
  localStorage.removeItem("moneyMovementToken");
  state.token = null;
  state.user = null;
  state.page = "balance";
  renderAuthState();
});

document.querySelector("#refreshButton").addEventListener("click", loadDashboard);

document.querySelector("#transferForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/api/transfers", {
    method: "POST",
    body: {
      receiver_username: form.get("receiver_username"),
      amount: form.get("amount"),
      idempotency_key: crypto.randomUUID(),
      note: form.get("note") || null,
    },
  });
  showToast("Transfer completed");
  event.currentTarget.reset();
  await loadDashboard();
  setDashboardPage("statements");
});

document.querySelector("#requestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/api/money-requests", {
    method: "POST",
    body: {
      payer_username: form.get("payer_username"),
      amount: form.get("amount"),
      note: form.get("note") || null,
    },
  });
  showToast("Money request created");
  event.currentTarget.reset();
  await loadDashboard();
  setDashboardPage("moneyRequests");
});

async function authenticate(path, body) {
  const response = await api(path, {
    method: "POST",
    body,
    publicRequest: true,
  });
  state.token = response.access_token;
  state.user = response.user;
  localStorage.setItem("moneyMovementToken", state.token);
  renderAuthState();
  await loadDashboard();
}

async function loadSession() {
  if (!state.token) {
    renderAuthState();
    return;
  }

  try {
    state.user = await api("/api/auth/me");
    renderAuthState();
    await loadDashboard();
  } catch {
    localStorage.removeItem("moneyMovementToken");
    state.token = null;
    state.user = null;
    renderAuthState();
  }
}

async function loadDashboard() {
  if (!state.token) {
    return;
  }

  const [wallet, requests, transactions] = await Promise.all([
    api("/api/wallet"),
    api("/api/money-requests"),
    api("/api/transfers/history"),
  ]);

  balanceText.textContent = formatMoney(wallet.balance);
  renderRequests(requests);
  renderTransactions(transactions);
}

function renderAuthState() {
  const signedIn = Boolean(state.token && state.user);
  authPanel.classList.toggle("hidden", signedIn);
  appPanel.classList.toggle("hidden", !signedIn);

  if (signedIn) {
    welcomeText.textContent = `Wallet for @${state.user.username}`;
    summaryUser.textContent = `@${state.user.username}`;
    summaryEmail.textContent = state.user.email;
    setDashboardPage(state.page);
  }
}

function setAuthMode(mode) {
  const login = mode === "login";
  loginForm.classList.toggle("hidden", !login);
  registerForm.classList.toggle("hidden", login);
  showLogin.classList.toggle("is-active", login);
  showRegister.classList.toggle("is-active", !login);
}

function setDashboardPage(page) {
  state.page = page;
  navButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.page === page);
  });
  pagePanels.forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.pagePanel !== page);
  });
}

function renderRequests(requests) {
  if (!requests.length) {
    requestsList.innerHTML = `<p class="empty">No money requests yet.</p>`;
    return;
  }

  requestsList.innerHTML = requests
    .map((request) => {
      const incoming = request.payer_id === state.user.id;
      const label = incoming ? "Incoming request" : "Outgoing request";
      const actions = incoming && request.status === "PENDING"
        ? `<div class="item-actions">
            <button type="button" data-action="accept" data-id="${request.id}">Accept</button>
            <button class="danger" type="button" data-action="reject" data-id="${request.id}">Reject</button>
          </div>`
        : "";

      return `<article class="item">
        <div class="item-head">
          <span>${label}</span>
          <span>${request.status}</span>
        </div>
        <div>${formatMoney(request.amount)}</div>
        <small>${escapeHtml(request.note || "No note")}</small>
        ${actions}
      </article>`;
    })
    .join("");

  requestsList.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.id;
      const action = button.dataset.action;

      if (action === "accept") {
        await api(`/api/money-requests/${id}/accept`, {
          method: "POST",
          body: {
            idempotency_key: crypto.randomUUID(),
          },
        });
        showToast("Request accepted and paid");
      } else {
        await api(`/api/money-requests/${id}/reject`, {
          method: "POST",
        });
        showToast("Request rejected");
      }

      await loadDashboard();
    });
  });
}

function renderTransactions(transactions) {
  if (!transactions.length) {
    transactionsList.innerHTML = `<p class="empty">No transactions yet.</p>`;
    return;
  }

  transactionsList.innerHTML = transactions
    .map((transaction) => {
      const outgoing = transaction.sender_id === state.user.id;
      const sign = outgoing ? "-" : "+";
      const direction = outgoing ? "Sent" : "Received";
      return `<article class="item">
        <div class="item-head">
          <span>${direction}</span>
          <span class="${outgoing ? "" : "success"}">${sign}${formatMoney(transaction.amount)}</span>
        </div>
        <small>${transaction.transaction_type} · ${new Date(transaction.created_at).toLocaleString()}</small>
        <div><small>${escapeHtml(transaction.note || "No note")}</small></div>
      </article>`;
    })
    .join("");
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (state.token && !options.publicRequest) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = "Request failed";

    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      message = response.statusText || message;
    }

    showToast(message);
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function formatMoney(value) {
  return `BDT ${Number(value).toLocaleString("en-BD", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 3200);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadSession();
