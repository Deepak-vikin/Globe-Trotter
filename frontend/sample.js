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
    loadUserTrips(user.email);
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

async function loadUserTrips(email) {
  const tripsSection = document.getElementById("userTripsSection");
  const tripsList = document.getElementById("userTripsList");
  if (!tripsSection || !tripsList) return;

  try {
    const res = await fetch(API + "/api/trips?email=" + encodeURIComponent(email));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load trips");

    const trips = data.trips || [];
    if (trips.length > 0) {
      tripsSection.style.display = "block";
      tripsList.innerHTML = trips.map(trip => {
        // Append time to prevent utc timezone shifting the day backwards
        const dObj = new Date(trip.start_date + "T00:00:00");
        const rObj = new Date(trip.return_date + "T00:00:00");
        const dStr = dObj.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        const rStr = rObj.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        const modeIcons = { flight: "✈️", train: "🚂", bus: "🚌" };
        const icon = modeIcons[trip.transport_mode] || "✈️";

        return `
          <div class="sq-card spot-card" style="display:flex; flex-direction:column; justify-content:center; padding: 20px; background: linear-gradient(135deg, rgba(255,255,255,0.15), rgba(255,255,255,0.05)); border: 1px solid rgba(255,255,255,0.3); align-items:flex-start;">
            <div style="font-size: 2rem; margin-bottom: 15px; display:flex; justify-content: space-between; width: 100%;">
              <span>${icon}</span>
              <div>
                <button onclick="editTrip('${encodeURIComponent(JSON.stringify(trip))}')" style="background:transparent; border:none; color:#00b4d8; cursor:pointer; margin-right:8px; font-size:1.1rem">✏️</button>
                <button onclick="deleteTrip(${trip.id})" style="background:transparent; border:none; color:#ff8787; cursor:pointer; font-size:1.1rem">🗑️</button>
              </div>
            </div>
            <h4 class="spot-name" style="font-size: 1.3rem; margin-bottom: 8px;">${trip.dest_city}</h4>
            <div style="font-size: 0.85rem; opacity: 0.8; margin-bottom: 15px;">${trip.dest_state || trip.dest_country}</div>
            <div style="font-size: 0.95rem; font-weight: 500; margin-top: auto; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); width: 100%;">
              <div><span style="opacity: 0.7; font-size: 0.8rem;">DATES</span></div>
              ${dStr} — ${rStr}
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Error loading user trips:", err);
  }
}

function editTrip(encodedTrip) {
  const trip = JSON.parse(decodeURIComponent(encodedTrip));
  sessionStorage.setItem("edit_trip", JSON.stringify(trip));
  document.body.style.transition = "opacity 0.4s ease";
  document.body.style.opacity = "0";
  setTimeout(() => location.href = "plan_trip.html", 400);
}

async function deleteTrip(tripId) {
  const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
  if (!user || !confirm("Are you sure you want to delete this trip?")) return;
  try {
    const res = await fetch(API + `/api/trips/${tripId}?email=${encodeURIComponent(user.email)}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete trip");
    loadUserTrips(user.email); // Reload trips
  } catch (err) {
    alert(err.message);
  }
}

/* ── Plan Trip ── */
const planTripForm    = document.getElementById("planTripForm");
const planTouristSpots = document.getElementById("planTouristSpots");
const tripCountry     = document.getElementById("tripCountry");
const tripState       = document.getElementById("tripState");
const tripCity        = document.getElementById("tripCity");

function formatDateDisplay(dateStr, mainId, subId) {
  if (!dateStr) return;
  const d = new Date(dateStr);
  if (isNaN(d)) return;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const dm = document.getElementById(mainId);
  const ds = document.getElementById(subId);
  if (dm) dm.innerHTML = `${d.getDate()} <span style="font-size:1rem; font-weight:500">${months[d.getMonth()]}'${d.getFullYear().toString().slice(-2)}</span>`;
  if (ds) ds.textContent = days[d.getDay()];
}

if (planTripForm) {
  const tripStart = document.getElementById("tripStart");
  const tripEnd   = document.getElementById("tripEnd");
  if (tripStart && tripEnd) {
    const now = new Date();
    const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0];
    tripStart.min = tomorrowStr;
    tripEnd.min   = tomorrowStr;
    tripStart.value = tomorrowStr;
    tripEnd.value = tomorrowStr;
    formatDateDisplay(tomorrowStr, "fwDateMain", "fwDateSub");
    formatDateDisplay(tomorrowStr, "fwReturnMain", "fwReturnSub");

    // Click on section opens the date picker
    const depSection = document.getElementById("fwDepartureSection");
    const retSection = document.getElementById("fwReturnSection");
    if (depSection) depSection.addEventListener("click", () => { try { tripStart.showPicker(); } catch(e) { tripStart.focus(); tripStart.click(); } });
    if (retSection) retSection.addEventListener("click", () => { try { tripEnd.showPicker(); } catch(e) { tripEnd.focus(); tripEnd.click(); } });

    tripStart.addEventListener("change", () => {
      tripEnd.min = tripStart.value;
      if (tripEnd.value && tripEnd.value < tripStart.value) {
        tripEnd.value = tripStart.value;
      }
      formatDateDisplay(tripStart.value, "fwDateMain", "fwDateSub");
      formatDateDisplay(tripEnd.value, "fwReturnMain", "fwReturnSub");
    });
    tripEnd.addEventListener("change", () => formatDateDisplay(tripEnd.value, "fwReturnMain", "fwReturnSub"));
  }

  const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
  if (!user) {
    location.href = "index.html";
  } else {
    const editTripData = JSON.parse(sessionStorage.getItem("edit_trip") || "null");
    const fromM = document.getElementById("fwFromMain");
    const fromS = document.getElementById("fwFromSub");
    if (fromM) fromM.textContent = user.city || "Current City";
    if (fromS) fromS.textContent = `${user.state || ""}, ${user.country || "India"}`;

    if (editTripData) {
      document.getElementById("makeNewTripBtn").textContent = "Update Trip";
      document.querySelector(".section-header h3").textContent = "Edit your trip";
      
      const tc = document.getElementById("tripCity");
      const ts = document.getElementById("tripState");
      const tco = document.getElementById("tripCountry");
      const gs = document.getElementById("globalPlaceSearch");
      const tsSub = document.getElementById("fwToSub");
      
      if (tc) tc.value = editTripData.dest_city;
      if (ts) ts.value = editTripData.dest_state;
      if (tco) tco.value = editTripData.dest_country;
      if (gs) gs.value = editTripData.dest_city;
      if (tsSub) tsSub.textContent = [editTripData.dest_state, editTripData.dest_country].filter(Boolean).join(", ");
      
      const tStart = document.getElementById("tripStart");
      const tEnd = document.getElementById("tripEnd");
      if (tStart) {
        tStart.value = editTripData.start_date;
        formatDateDisplay(tStart.value, "fwDateMain", "fwDateSub");
      }
      if (tEnd) {
        tEnd.value = editTripData.return_date;
        tEnd.min = editTripData.start_date;
        formatDateDisplay(tEnd.value, "fwReturnMain", "fwReturnSub");
      }
      
      window.selectedTransportMode = editTripData.transport_mode;
      document.querySelectorAll(".transport-option").forEach(o => o.classList.remove("active"));
      const activeOpt = document.querySelector(`.transport-option[data-mode="${editTripData.transport_mode}"]`);
      if (activeOpt) activeOpt.classList.add("active");
    }

    loadPlanTripRecommendations(user.email);
  }

  planTripForm.onsubmit = async e => {
    e.preventDefault();
    const btn = document.getElementById("makeNewTripBtn");
    btn.textContent = "Creating Trip...";

    const destCity    = (document.getElementById("tripCity")    || {}).value || (document.getElementById("globalPlaceSearch") || {}).value || "";
    const destState   = (document.getElementById("tripState")   || {}).value || "";
    const destCountry = (document.getElementById("tripCountry") || {}).value || "";
    const startDate   = (document.getElementById("tripStart")   || {}).value || "";
    const returnDate  = (document.getElementById("tripEnd")     || {}).value || "";
    const mode        = window.selectedTransportMode || "flight";

    if (!destCity.trim()) {
      status("planTripStatus", "error", "Please select a destination.");
      btn.textContent = "Make a Trip";
      return;
    }
    if (!startDate || !returnDate) {
      status("planTripStatus", "error", "Please select departure and return dates.");
      btn.textContent = "Make a Trip";
      return;
    }

    try {
      const payload = {
        email: user.email,
        dest_city: destCity.trim(),
        dest_state: destState.trim(),
        dest_country: destCountry.trim(),
        start_date: startDate,
        return_date: returnDate,
        transport_mode: mode
      };
      
      if (editTripData) {
        // PUT request for update
        const res = await fetch(API + `/api/trips/${editTripData.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to update trip.");
        status("planTripStatus", "success", "Trip updated successfully! ✈️");
        sessionStorage.removeItem("edit_trip");
      } else {
        // POST request for new trip
        await apiPost("/api/trips", payload);
        status("planTripStatus", "success", "Trip created successfully! ✈️");
      }
      
      setTimeout(() => {
        document.body.style.transition = "opacity 0.6s ease";
        document.body.style.opacity = "0";
        setTimeout(() => location.href = "landing.html", 600);
      }, 1200);
    } catch (err) {
      status("planTripStatus", "error", err.message || "Failed to create trip.");
      btn.textContent = "Make a Trip";
    }
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
    window.currentTripSpots = spots;
    renderPlanTouristSpots(spots);
  } catch (err) {
    planTouristSpots.innerHTML = `<p style="opacity:.7;width:100%;text-align:center">${err.message || "Failed to load."}</p>`;
  }
}

function renderPlanTouristSpots(spots) {
  if (!planTouristSpots) return;
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
}

const globalSearch = document.getElementById("globalPlaceSearch");
const globalList = document.getElementById("globalPlaceList");
if (globalSearch && globalList) {
  let debounceTimer;
  globalSearch.addEventListener("input", e => {
    const val = e.target.value.trim();
    globalList.innerHTML = "";
    if (val.length < 3) { globalList.classList.remove("show"); return; }
    
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(val)}&format=json&addressdetails=1&limit=5`);
        const data = await res.json();
        if (!data || !data.length) { globalList.classList.remove("show"); return; }
        
        globalList.classList.add("show");
        globalList.innerHTML = data.map(item => {
          const addr = item.address || {};
          const city = addr.city || addr.town || addr.village || addr.county || "";
          const state = addr.state || "";
          const country = addr.country || "";
          return `<div data-city="${city.replace(/"/g, '&quot;')}" data-state="${state.replace(/"/g, '&quot;')}" data-country="${country.replace(/"/g, '&quot;')}">${item.display_name}</div>`;
        }).join("");
        
        Array.from(globalList.children).forEach(div => {
          div.onmousedown = (ev) => {
            ev.preventDefault();
            globalSearch.value = div.textContent;
            globalList.classList.remove("show");
            
            const cc = div.getAttribute("data-country") || "";
            const ss = div.getAttribute("data-state") || "";
            const ct = div.getAttribute("data-city") || "";
            if (tripCountry) tripCountry.value = cc;
            if (tripState) tripState.value = ss;
            if (tripCity) tripCity.value = ct;
            
            const toSub = document.getElementById("fwToSub");
            if (toSub) {
              const parts = [ss, cc].filter(Boolean);
              toSub.textContent = parts.join(", ") || "Selected Destination";
            }
          };
        });
      } catch (err) { console.error(err); }
    }, 400);
  });
  
  document.addEventListener("click", ev => {
    if (!ev.target.closest("#globalPlaceSearch")) {
      globalList.classList.remove("show");
    }
  });
}

window.selectSpot = function(encodedCity, encodedState, encodedCountry) {
  const ct = decodeURIComponent(encodedCity);
  let st = decodeURIComponent(encodedState);
  let co = decodeURIComponent(encodedCountry);

  const gs = document.getElementById("globalPlaceSearch");
  if (gs) gs.value = ct;

  if (tripCity) tripCity.value = ct;
  if (!st || !co) {
    const user = JSON.parse(sessionStorage.getItem("gt_user") || "null");
    if (user) {
      if (!st && tripState) st = user.state || "";
      if (!co && tripCountry) co = user.country || "";
    }
  }
  if (tripState) tripState.value = st;
  if (tripCountry) tripCountry.value = co;

  const toSub = document.getElementById("fwToSub");
  if (toSub) {
    const parts = [st, co].filter(Boolean);
    toSub.textContent = parts.join(", ") || "Selected Destination";
  }
};

/* ── Transport Mode Toggle ── */
const transportModes = document.getElementById("transportModes");
if (transportModes) {
  window.selectedTransportMode = "flight";
  transportModes.addEventListener("click", e => {
    const opt = e.target.closest(".transport-option");
    if (!opt) return;
    transportModes.querySelectorAll(".transport-option").forEach(o => o.classList.remove("active"));
    opt.classList.add("active");
    window.selectedTransportMode = opt.dataset.mode;
  });
}