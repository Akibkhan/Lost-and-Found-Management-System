//----------------------------------------------------
// DOM ELEMENTS
//----------------------------------------------------
const resultsContainer = document.getElementById("results-container");
const paginationContainer = document.getElementById("pagination");
const skeletonTemplate = document.getElementById("skeleton-template");
const searchBtn = document.getElementById("search-btn");
const clearBtn = document.getElementById("clear-btn");

const queryInput = document.getElementById("query");
const categorySelect = document.getElementById("category");
const radiusInput = document.getElementById("radius");
const latField = document.getElementById("lat");
const lonField = document.getElementById("lon");

let currentPage = 1;
let isLoading = false;


//----------------------------------------------------
// LEAFLET MAP
//----------------------------------------------------
let map = L.map("map", {
    dragging: true,
    scrollWheelZoom: true,
    tap: false
}).setView([20.5937, 78.9629], 5);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let marker = null;
let radiusCircle = null;

// When user clicks on map
map.on("click", (e) => {
    setMarker(e.latlng);
});

// Set marker function
function setMarker(latlng) {
    if (marker) map.removeLayer(marker);
    if (radiusCircle) map.removeLayer(radiusCircle);

    marker = L.marker(latlng, { draggable: true }).addTo(map);

    latField.value = latlng.lat;
    lonField.value = latlng.lng;

    updateCircle(latlng);

    // Update lat/lon when dragging
    marker.on("drag", (ev) => {
        const newLatLng = ev.target.getLatLng();
        latField.value = newLatLng.lat;
        lonField.value = newLatLng.lng;
        updateCircle(newLatLng);
    });
}

// Draw/update radius circle
function updateCircle(latlng) {
    const rad = parseFloat(radiusInput.value) || 0;

    if (radiusCircle) map.removeLayer(radiusCircle);

    if (rad > 0) {
        radiusCircle = L.circle(latlng, {
            radius: rad * 1000, // km → meters
            color: "#0d6efd",
            fillOpacity: 0.25
        }).addTo(map);
    }
}

// Update circle when radius input changes
radiusInput.addEventListener("input", () => {
    if (marker) {
        updateCircle(marker.getLatLng());
    }
});


//----------------------------------------------------
// SKELETON LOADER
//----------------------------------------------------
function showSkeleton() {
    resultsContainer.innerHTML = "";
    for (let i = 0; i < 6; i++) {
        resultsContainer.appendChild(
            skeletonTemplate.content.cloneNode(true)
        );
    }
}


//----------------------------------------------------
// CREATE CARD
//----------------------------------------------------
function createCard(item) {
    let img = item.photo || "https://via.placeholder.com/400?text=No+Image";

    return `
    <div class="col-md-4 mb-4 item-card">
      <div class="card h-100 shadow-sm hover-shadow">
        <img src="${img}" class="card-img-top" alt="${item.name}"
             onerror="this.src='https://via.placeholder.com/400?text=No+Image'">
        <div class="card-body d-flex flex-column">
          <h5 class="card-title">${item.name}</h5>
          <p class="card-text text-muted">
            ${item.description ? item.description.substring(0, 100) : ""}...
          </p>
          <div class="mt-auto">
            <span class="badge bg-primary">${item.status || ""}</span>
            <span class="badge bg-light text-dark">
              ${item.category || ""}
            </span>
            ${
                item.distance !== null && item.distance !== undefined
                ? `<p class="mt-2"><small>📍 ${item.distance.toFixed(1)} km</small></p>`
                : ""
            }
            <a href="/item/${item.id}" class="btn btn-primary btn-sm mt-2">
              View
            </a>
          </div>
        </div>
      </div>
    </div>`;
}


//----------------------------------------------------
// RENDER RESULTS
//----------------------------------------------------
function renderResults(data) {
    resultsContainer.innerHTML = "";

    if (!data.items || !data.items.length) {
        resultsContainer.innerHTML =
            `<p class="text-center mt-4">No results found.</p>`;
        paginationContainer.innerHTML = "";
        return;
    }

    data.items.forEach(item => {
        resultsContainer.innerHTML += createCard(item);
    });

    // Masonry Layout
    new Masonry(resultsContainer, {
        itemSelector: ".item-card",
        percentPosition: true,
        transitionDuration: "0.3s"
    });

    renderPagination(data.page, data.pages);
}


//----------------------------------------------------
// PAGINATION
//----------------------------------------------------
function renderPagination(page, total) {
    paginationContainer.innerHTML = "";

    if (total <= 1) return;

    if (page > 1) {
        paginationContainer.innerHTML +=
            `<button onclick="fetchResults(${page - 1})">Prev</button>`;
    }

    for (let i = 1; i <= total; i++) {
        paginationContainer.innerHTML +=
            `<button class="${i === page ? 'active' : ''}"
                onclick="fetchResults(${i})">${i}</button>`;
    }

    if (page < total) {
        paginationContainer.innerHTML +=
            `<button onclick="fetchResults(${page + 1})">Next</button>`;
    }
}


//----------------------------------------------------
// FETCH RESULTS
//----------------------------------------------------
function fetchResults(page = 1) {

    if (isLoading) return;

    isLoading = true;
    showSkeleton();
    searchBtn.classList.add("loading");

    let q = encodeURIComponent(queryInput.value || "");
    let c = categorySelect.value
        ? encodeURIComponent(categorySelect.value)
        : "";
    let r = radiusInput.value || "";
    let lat = latField.value || "";
    let lon = lonField.value || "";

    fetch(`/search?query=${q}&category=${c}&radius=${r}&lat=${lat}&lon=${lon}&page=${page}`)
        .then(res => res.json())
        .then(data => {
            renderResults(data);
            isLoading = false;
            searchBtn.classList.remove("loading");

            // Update URL correctly
            history.pushState(
                {},
                "",
                `/search?query=${q}&category=${c}&radius=${r}&lat=${lat}&lon=${lon}&page=${page}`
            );
        })
        .catch(err => {
            console.error("Search error:", err);
            isLoading = false;
            searchBtn.classList.remove("loading");
        });
}


//----------------------------------------------------
// EVENTS
//----------------------------------------------------
searchBtn.addEventListener("click", () => fetchResults(1));

queryInput.addEventListener("keyup", (e) => {
    if (e.key === "Enter") fetchResults(1);
});

clearBtn.addEventListener("click", () => {
    queryInput.value = "";
    categorySelect.value = "";
    radiusInput.value = "5";
    latField.value = "";
    lonField.value = "";

    resultsContainer.innerHTML = "";
    paginationContainer.innerHTML = "";

    if (marker) map.removeLayer(marker);
    if (radiusCircle) map.removeLayer(radiusCircle);

    marker = null;
    radiusCircle = null;

    history.pushState({}, "", "/search");
});
