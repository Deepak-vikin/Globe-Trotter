"use strict";

const API = "http://localhost:8000";

async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || "Server error"), { status: res.status });
  return data;
}

function status(id, type, msg) {
  const el = document.getElementById(id);
  if (el) { el.className = "status " + type; el.textContent = msg; }
}

/* ── Login ── */
const loginForm   = document.getElementById("loginForm");
const toggleBtn   = document.getElementById("togglePasswordBtn");
const loginPwd    = document.getElementById("loginPassword");

if (toggleBtn && loginPwd) {
  toggleBtn.onclick = () => {
    loginPwd.type = loginPwd.type === "password" ? "text" : "password";
  };
}

if (loginForm) {
  loginForm.onsubmit = async e => {
    e.preventDefault();
    loginBtn.textContent = "Signing in…";
    try {
      const user = await apiPost("/api/login", {
        email: loginEmail.value.trim(),
        password: loginPassword.value
      });
      sessionStorage.setItem("gt_user", JSON.stringify(user));
      status("loginStatus", "success", `Welcome back, ${user.name}! ✈`);
      setTimeout(() => location.href = "landing.html", 800);
    } catch (err) {
      status("loginStatus", "error", err.message);
    }
    loginBtn.textContent = "Sign In";
  };
}

/* ── Autocomplete helpers ── */
let cacheC = [], cacheS = {}, cacheCity = {};

async function fetchC() {
  if (cacheC.length) return cacheC;
  const d = await fetch("https://countriesnow.space/api/v0.1/countries/iso")
    .then(r => r.json()).catch(() => ({}));
  cacheC = d?.data?.map(i => i.name) || [];
  return cacheC;
}

async function fetchS(country) {
  if (cacheS[country]) return cacheS[country];
  const d = await fetch("https://countriesnow.space/api/v0.1/countries/states", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ country })
  }).then(r => r.json()).catch(() => ({}));
  cacheS[country] = d?.data?.states?.map(i => i.name) || [];
  return cacheS[country];
}

async function fetchCity(country, state) {
  const key = country + "|" + state;
  if (cacheCity[key]) return cacheCity[key];
  const d = await fetch("https://countriesnow.space/api/v0.1/countries/state/cities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ country, state })
  }).then(r => r.json()).catch(() => ({}));
  cacheCity[key] = d?.data || [];
  return cacheCity[key];
}

function setupAutocomplete(inputEl, listEl, fetchFn, onSelect) {
  if (!inputEl) return;
  inputEl.addEventListener("input", async e => {
    const val = e.target.value;
    listEl.innerHTML = "";
    if (!val.trim()) { listEl.classList.remove("show"); return; }
    const matches = (await fetchFn()).filter(i => i.toLowerCase().startsWith(val.trim().toLowerCase()));
    if (!matches.length) { listEl.classList.remove("show"); return; }
    listEl.classList.add("show");
    listEl.innerHTML = matches.slice(0, 10).map(m => `<div>${m}</div>`).join("");
    Array.from(listEl.children).forEach(div => {
      div.onmousedown = e => {
        e.preventDefault();
        inputEl.value = div.textContent;
        listEl.classList.remove("show");
        if (onSelect) onSelect(div.textContent);
      };
    });
  });
}

/* ── Register ── */
const registerForm = document.getElementById("registerForm");

if (registerForm) {
  const cList = document.getElementById("countryList");
  const sList = document.getElementById("stateList");
  const cityList = document.getElementById("cityList");

  setupAutocomplete(regCountry, cList, fetchC, () => { regState.value = ""; regCity.value = ""; });
  setupAutocomplete(regState, sList, () => fetchS(regCountry.value), () => { regCity.value = ""; });
  setupAutocomplete(regCity, cityList, () => fetchCity(regCountry.value, regState.value), null);

  document.addEventListener("click", e => {
    if (!e.target.closest(".autocomplete")) {
      [cList, sList, cityList].forEach(l => l && l.classList.remove("show"));
    }
  });

  registerForm.onsubmit = async e => {
    e.preventDefault();
    if (regPassword.value !== regConfirm.value)
      return status("registerStatus", "error", "Passwords do not match.");
    registerBtn.textContent = "Creating…";
    try {
      const data = {
        name: regName.value.trim(), email: regEmail.value.trim(),
        password: regPassword.value, city: regCity.value.trim(),
        state: regState.value.trim(), country: regCountry.value.trim()
      };
      await apiPost("/api/register", data);
      status("registerStatus", "success", `Account created! Welcome, ${data.name} 🌍`);
      setTimeout(() => location.href = "index.html", 1300);
    } catch (err) {
      status("registerStatus", err.status === 409 ? "warning" : "error", err.message);
    }
    registerBtn.textContent = "Create My Account";
  };
}

/* ── Landing ── */
const touristSpotsContainer = document.getElementById("touristSpots");
const planTripBtn = document.getElementById("planTripBtn");

if (planTripBtn) {
  planTripBtn.onclick = () => {
    document.body.style.transition = "opacity 0.4s ease";
    document.body.style.opacity = "0";
    setTimeout(() => location.href = "plan_trip.html", 400);
  };
}

if (touristSpotsContainer) {
  const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
  if (!user) {
    location.href = "index.html";
  } else {
    const logo = document.querySelector(".navbar .logo");
    if (logo) logo.innerHTML = `GlobeTrotter<span style="font-size:1rem;display:block;margin-top:4px">Welcome, ${user.name}</span>`;
    const regionEl = document.getElementById("regionName");
    if (regionEl) regionEl.textContent = "India";
    loadRecommendations(user.email, "India");
  }
}

async function loadRecommendations(email, regionLabel) {
  if (!touristSpotsContainer) return;
  touristSpotsContainer.innerHTML = Array(5).fill(
    `<div class="sq-card shimmer-card"><div class="shimmer"></div></div>`
  ).join("");
  try {
    const res = await fetch(API + "/api/recommendations?email=" + encodeURIComponent(email));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load");
    const regionEl = document.getElementById("regionName");
    if (regionEl && data.region) regionEl.textContent = data.region;
    const spots = data.spots || [];
    if (!spots.length) {
      touristSpotsContainer.innerHTML = `<p style="opacity:.7;font-style:italic">No tourist spots found in ${regionLabel}.</p>`;
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
    touristSpotsContainer.innerHTML = `
      <div style="width:100%;text-align:center;padding:20px">
        <p style="opacity:.8;margin-bottom:12px">${err.message}</p>
        <button class="fab" style="position:static;padding:8px 16px;font-size:.9rem"
          onclick="loadRecommendations('${email}','${regionLabel.replace(/'/g,"\\'")}')">
          Try Again
        </button>
      </div>`;
  }
}

/* ── Plan Trip ── */
const planTripForm    = document.getElementById("planTripForm");
const planTouristSpots = document.getElementById("planTouristSpots");
const tripCountry     = document.getElementById("tripCountry");
const tripState       = document.getElementById("tripState");
const tripCity        = document.getElementById("tripCity");

if (planTripForm) {
  const cList    = document.getElementById("tripCountryList");
  const sList    = document.getElementById("tripStateList");
  const cityList = document.getElementById("tripCityList");

  setupAutocomplete(tripCountry, cList, fetchC, () => { tripState.value = ""; tripCity.value = ""; });
  setupAutocomplete(tripState, sList, () => fetchS(tripCountry.value), () => { tripCity.value = ""; });
  setupAutocomplete(tripCity, cityList, () => fetchCity(tripCountry.value, tripState.value), null);

  const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
  if (!user) location.href = "index.html";
  else loadPlanTripRecommendations(user.email);

  planTripForm.onsubmit = e => {
    e.preventDefault();
    document.getElementById("makeNewTripBtn").textContent = "Creating Trip...";
    status("planTripStatus", "success", "Trip planned! Preparing itinerary…");
    setTimeout(() => {
      document.body.style.transition = "opacity 0.6s ease";
      document.body.style.opacity = "0";
      setTimeout(() => location.href = "landing.html", 600);
    }, 1500);
  };
}

async function loadPlanTripRecommendations(email) {
  if (!planTouristSpots) return;
  planTouristSpots.innerHTML = Array(5).fill(
    `<div class="sq-card shimmer-card"><div class="shimmer"></div></div>`
  ).join("");
  try {
    const res = await fetch(API + "/api/recommendations?email=" + encodeURIComponent(email));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load");
    const spots = data.spots || [];
    if (!spots.length) {
      planTouristSpots.innerHTML = `<p style="opacity:.7;width:100%;text-align:center">No spots found.</p>`;
      return;
    }
    planTouristSpots.innerHTML = spots.map((spot, i) => `
      <div class="sq-card spot-card"
        onclick="selectSpot('${encodeURIComponent(spot.name)}','${encodeURIComponent(spot.state||'')}','${encodeURIComponent(spot.country||'')}')">
        <div class="spot-rank">#${i + 1}</div>
        <div class="spot-img" style="background-image:url('${spot.image}')"></div>
        <div class="spot-info">
          <h4 class="spot-name">${spot.name}</h4>
          <span class="spot-type">${spot.type}</span>
        </div>
      </div>
    `).join("");
  } catch (err) {
    planTouristSpots.innerHTML = `<p style="opacity:.7;width:100%;text-align:center">${err.message || "Failed to load."}</p>`;
  }
}

window.selectSpot = function(encodedCity, encodedState, encodedCountry) {
  if (!tripCity) return;
  tripCity.value = decodeURIComponent(encodedCity);
  const state   = decodeURIComponent(encodedState);
  const country = decodeURIComponent(encodedCountry);
  if (state && tripState)   tripState.value   = state;
  if (country && tripCountry) tripCountry.value = country;
  if (!state || !country) {
    const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
    if (user) {
      if (tripState && !state)     tripState.value   = user.state   || "";
      if (tripCountry && !country) tripCountry.value = user.country || "";
    }
  }
};