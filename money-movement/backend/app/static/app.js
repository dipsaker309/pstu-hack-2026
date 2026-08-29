const state = {
  token: localStorage.getItem("moneyMovementToken"),
  user: null,
};

const authPanel = document.querySelector("#authPanel");
const appPanel = document.querySelector("#appPanel");
const toast = document.querySelector("#toast");
const welcomeText = document.querySelector("#welcomeText");
const balanceText = document.querySelector("#balanceText");
const requestsList = document.querySelector("#requestsList");
const transactionsList = document.querySelector("#transactionsList");

document.querySelector("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await authenticate("/api/auth/register", {
    username: form.get("username"),
    email: form.get("email"),
    password: form.get("password"),
  });
  event.currentTarget.reset();
});

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
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
  }
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
