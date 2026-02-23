"use strict";

const API = "http://localhost:8000";

async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || "Server error"), { status: res.status });
  return data;
}

function status(id, type, msg) {
  const el = document.getElementById(id);
  if (el) { el.className = "status " + type; el.textContent = msg; }
}

// ── LOGIN ──
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    document.getElementById("loginBtn").textContent = "Signing in…";
    try {
      const user = await apiPost("/api/login", { email, password });
      status("loginStatus", "success", `Welcome back, ${user.name}! ✈`);
      sessionStorage.setItem("gt_user", JSON.stringify(user));
    } catch (err) {
      status("loginStatus", "error", err.message);
    } finally {
      document.getElementById("loginBtn").textContent = "Sign In";
    }
  });
}

// ── REGISTER ──
const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("regName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const password = document.getElementById("regPassword").value;
    const confirm = document.getElementById("regConfirm").value;
    const city = document.getElementById("regCity").value.trim();
    const state = document.getElementById("regState").value.trim();
    const country = document.getElementById("regCountry").value.trim();

    if (password !== confirm)
      return status("registerStatus", "error", "Passwords do not match.");

    document.getElementById("registerBtn").textContent = "Creating…";
    try {
      await apiPost("/api/register", { name, email, password, city, state, country });
      status("registerStatus", "success", `Account created! Welcome, ${name} 🌍`);
      setTimeout(() => window.location.href = "index.html", 1800);
    } catch (err) {
      status("registerStatus", err.status === 409 ? "warning" : "error", err.message);
    } finally {
      document.getElementById("registerBtn").textContent = "Create My Account";
    }
  });
}
