"use strict";

const API = "http://localhost:8000";

async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(
    new Error(data.detail || "Server error"),
    { status: res.status }
  );
  return data;
}

function status(id, type, msg) {
  const el = document.getElementById(id);
  if (el) {
    el.className = "status " + type;
    el.textContent = msg;
  }
}

/* ---------------- LOGIN ---------------- */

const loginForm = document.getElementById("loginForm");
const toggleBtn = document.getElementById("togglePasswordBtn");
const loginPwd = document.getElementById("loginPassword");

if (toggleBtn && loginPwd) {
  toggleBtn.onclick = () => {
    loginPwd.type = loginPwd.type === "password" ? "text" : "password";
  };
}

if (loginForm) {
  loginForm.onsubmit = async e => {
    e.preventDefault();
    const email = loginEmail.value.trim();
    const password = loginPassword.value;

    loginBtn.textContent = "Signing in…";
    try {
      const user = await apiPost("/api/login", { email, password });
      sessionStorage.setItem("gt_user", JSON.stringify(user));
      status("loginStatus", "success", `Welcome back, ${user.name}! ✈`);
      setTimeout(() => location.href = "landing.html", 800);
    } catch (err) {
      status("loginStatus", "error", err.message);
    }
    loginBtn.textContent = "Sign In";
  };
}

/* ---------------- REGISTER ---------------- */

const registerForm = document.getElementById("registerForm");
let cacheC = [], cacheS = {}, cacheCity = {};

async function fetchC() {
  if (cacheC.length) return cacheC;
  const r = await fetch("https://countriesnow.space/api/v0.1/countries/iso");
  const d = await r.json().catch(() => ({}));
  cacheC = d?.data?.map(i => i.name) || [];
  return cacheC;
}

async function fetchS(country) {
  if (cacheS[country]) return cacheS[country];
  const r = await fetch("https://countriesnow.space/api/v0.1/countries/states", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ country })
  });
  const d = await r.json().catch(() => ({}));
  cacheS[country] = d?.data?.states?.map(i => i.name) || [];
  return cacheS[country];
}

async function fetchCity(country, state) {
  const key = country + "|" + state;
  if (cacheCity[key]) return cacheCity[key];
  const r = await fetch("https://countriesnow.space/api/v0.1/countries/state/cities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ country, state })
  });
  const d = await r.json().catch(() => ({}));
  cacheCity[key] = d?.data || [];
  return cacheCity[key];
}

function setupAutocomplete(inputEl, listEl, fetchFn, onSelect) {
  if (!inputEl) return;
  inputEl.addEventListener("input", async e => {
    const val = e.target.value;
    listEl.innerHTML = "";
    if (!val.trim()) {
      listEl.classList.remove("show");
      return;
    }
    const items = await fetchFn();
    const matches = items.filter(i => i.toLowerCase().startsWith(val.trim().toLowerCase()));
    if (matches.length === 0) {
      listEl.classList.remove("show");
      return;
    }
    listEl.classList.add("show");
    listEl.innerHTML = matches.slice(0, 10).map(m => `<div>${m}</div>`).join("");

    Array.from(listEl.children).forEach(div => {
      div.onmousedown = (e) => {
        e.preventDefault();
        inputEl.value = div.textContent;
        listEl.classList.remove("show");
        if (onSelect) onSelect(div.textContent);
      };
    });
  });
}

if (registerForm) {
  const cList = document.getElementById("countryList");
  const sList = document.getElementById("stateList");
  const cityList = document.getElementById("cityList");

  setupAutocomplete(regCountry, cList, fetchC, (c) => {
    regState.value = "";
    regCity.value = "";
  });

  setupAutocomplete(regState, sList, () => fetchS(regCountry.value), (s) => {
    regCity.value = "";
  });

  setupAutocomplete(regCity, cityList, () => fetchCity(regCountry.value, regState.value), null);

  document.addEventListener("click", e => {
    if (e.target.parentElement && e.target.parentElement.className !== "autocomplete-items" && e.target.parentElement.parentElement?.className !== "autocomplete" && e.target.className !== "autocomplete-items") {
      if (cList) cList.classList.remove("show");
      if (sList) sList.classList.remove("show");
      if (cityList) cityList.classList.remove("show");
    }
  });

  registerForm.onsubmit = async e => {
    e.preventDefault();

    const data = {
      name: regName.value.trim(),
      email: regEmail.value.trim(),
      password: regPassword.value,
      city: regCity.value.trim(),
      state: regState.value.trim(),
      country: regCountry.value.trim()
    };

    if (regPassword.value !== regConfirm.value)
      return status("registerStatus", "error", "Passwords do not match.");

    registerBtn.textContent = "Creating…";
    try {
      await apiPost("/api/register", data);
      status("registerStatus", "success", `Account created! Welcome, ${data.name} 🌍`);
      setTimeout(() => location.href = "index.html", 1300);
    } catch (err) {
      status("registerStatus",
        err.status === 409 ? "warning" : "error",
        err.message
      );
    }
    registerBtn.textContent = "Create My Account";
  };
}

/* ---------------- LANDING ---------------- */

const touristSpotsContainer = document.getElementById("touristSpots");

if (touristSpotsContainer) {
  const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
  if (!user) location.href = "index.html";
  else {
    const logo = document.querySelector(".navbar .logo");
    if (logo)
      logo.innerHTML = `GlobeTrotter
      <span style="font-size:1rem;display:block;margin-top:4px">
      Welcome, ${user.name}</span>`;

    // --- Load tourist recommendations ---
    loadRecommendations(user.email);
  }
}

async function loadRecommendations(email) {
  if (!touristSpotsContainer) return;

  // Show shimmer loading cards
  touristSpotsContainer.innerHTML = Array(5).fill(
    `<div class="sq-card shimmer-card"><div class="shimmer"></div></div>`
  ).join("");

  try {
    const res = await fetch(API + "/api/recommendations?email=" + encodeURIComponent(email));
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || "Failed to load");

    // Update the section heading with the user's region/state
    const regionEl = document.getElementById("regionName");
    if (regionEl && data.region) regionEl.textContent = data.region;

    const spots = data.spots || [];
    if (spots.length === 0) {
      touristSpotsContainer.innerHTML =
        `<p style="opacity:.7;font-style:italic">No tourist spots found in your region.</p>`;
      return;
    }

    touristSpotsContainer.innerHTML = spots.map((spot, i) => `
      <div class="sq-card spot-card">
        <div class="spot-rank">#${i + 1}</div>
        <div class="spot-img" style="background-image:url('${spot.image}')"></div>
        <div class="spot-info">
          <h4 class="spot-name">${spot.name}</h4>
          <span class="spot-type">${spot.type}</span>
        </div>
      </div>
    `).join("");

  } catch (err) {
    console.error("Recommendations error:", err);
    touristSpotsContainer.innerHTML =
      `<p style="opacity:.7;font-style:italic">Could not load recommendations.</p>`;
  }
}