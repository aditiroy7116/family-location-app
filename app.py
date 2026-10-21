import os
import time
import secrets
from functools import wraps
from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, render_template_string
)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)

FAMILY_PASSWORD = os.environ.get("FAMILY_PASSWORD")
if not FAMILY_PASSWORD:
    raise RuntimeError(
        "Set FAMILY_PASSWORD in your terminal before starting the app."
    )

# Temporary storage: locations are cleared when the server restarts.
locations = {}
LOCATION_MAX_AGE = 120


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def protect_requests():
    if request.endpoint in ("login", "static") or request.method in ("GET", "HEAD", "OPTIONS"):
        return None

    if not session.get("logged_in"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Please log in."}), 401
        return redirect(url_for("login"))

    supplied = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    if not supplied or supplied != session.get("csrf_token"):
        return jsonify({
            "error": "Request could not be verified. Refresh the page and try again."
        }), 403


LOGIN_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Family Location · Login</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#081321;color:#edf7ff;font-family:Arial,sans-serif;padding:20px}
.card{width:100%;max-width:410px;padding:32px;border:1px solid #203b50;
border-radius:22px;background:#102235;box-shadow:0 20px 70px #0005}
.logo{font-size:35px}h1{margin:12px 0 8px}
p{color:#9db2c6;line-height:1.6}
label{display:block;margin:20px 0 8px}
input{width:100%;padding:13px;border-radius:10px;border:1px solid #34536a;
background:#081827;color:white;font-size:16px}
button{width:100%;padding:14px;margin-top:18px;border:0;border-radius:10px;
background:#25d5bd;color:#06201f;font-weight:bold;font-size:16px;cursor:pointer}
.error{color:#ff9caa}
</style>
</head>
<body>
<main class="card">
<div class="logo">⌖</div>
<h1>Family Location</h1>
<p>Sign in to view the family dashboard or share your location.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post">
<input type="hidden" name="csrf_token" value="{{ csrf }}">
<label for="password">Family password</label>
<input id="password" name="password" type="password" required
autocomplete="current-password" placeholder="Enter family password">
<button type="submit">Sign in</button>
</form>
</main>
</body>
</html>
"""


SHARE_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Share Location · Family Location</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#081321;color:#edf7ff;font-family:Arial,sans-serif;padding:24px}
main{max-width:650px;margin:auto}
nav{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:25px}
a{color:#47e0cf;text-decoration:none}
.card{padding:25px;border-radius:18px;border:1px solid #203b50;
background:#102235;margin:16px 0}
h1{margin-bottom:8px}p{color:#a8bdce;line-height:1.6}
label{display:block;margin:14px 0 7px}
input{width:100%;padding:13px;border-radius:9px;border:1px solid #34536a;
background:#081827;color:white;font-size:16px}
button{padding:13px 18px;border:0;border-radius:9px;font-weight:bold;
cursor:pointer;margin:8px 6px 0 0}
.start{background:#25d5bd;color:#06201f}
.stop{background:#ff8d9c;color:#351017}
.status{padding:12px;background:#081827;border-radius:9px;margin-top:15px}
</style>
</head>
<body>
<main>
<nav><a href="/dashboard">← Dashboard</a><a href="/logout">Log out</a></nav>
<h1>Share your location</h1>
<p>Your location is shared only after you choose Start Sharing.
Keep this page open while sharing.</p>
<div class="card">
<label for="member">Your name</label>
<input id="member" maxlength="60" placeholder="e.g. Adi" required>
<p>Use a name your family will recognize.</p>
<button class="start" id="start">Start Sharing</button>
<button class="stop" id="stop" disabled>Stop Sharing</button>
<div class="status" id="status">Location sharing is off.</div>
</div>
</main>
<script>
const csrf = {{ csrf|tojson }};
let watchId = null;
let activeName = "";
let sending = false;
const statusBox = document.getElementById("status");
const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const nameInput = document.getElementById("member");

function status(message) { statusBox.textContent = message; }

async function sendLocation(position) {
    if (!activeName || !sending) return;
    const payload = {
        name: activeName,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy
    };
    try {
        const response = await fetch("/api/location", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf
            },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            let detail = "Could not save location.";
            try {
                const result = await response.json();
                if (result.error) detail = result.error;
            } catch (_) {}
            throw new Error(detail + " (HTTP " + response.status + ")");
        }
        status("Sharing is on · Last update: " + new Date().toLocaleTimeString());
    } catch (error) {
        status(error.message);
    }
}

function locationError(error) {
    const messages = {
        1: "Location permission was denied. Allow it in your browser settings.",
        2: "Your current location is unavailable. Try again shortly.",
        3: "Location request timed out. Waiting for another update."
    };
    status(messages[error.code] || "Could not access location.");
}

startButton.addEventListener("click", () => {
    const name = nameInput.value.trim();
    if (!name) {
        status("Enter your name first.");
        nameInput.focus();
        return;
    }
    if (!navigator.geolocation) {
        status("This browser does not support location sharing.");
        return;
    }
    if (sending) return;

    activeName = name;
    sending = true;
    startButton.disabled = true;
    stopButton.disabled = false;
    nameInput.disabled = true;
    status("Requesting location permission…");

    watchId = navigator.geolocation.watchPosition(
        sendLocation,
        locationError,
        { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
    );
});

stopButton.addEventListener("click", async () => {
    sending = false;
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = null;

    try {
        const response = await fetch("/api/location", {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf
            },
            body: JSON.stringify({name: activeName})
        });
        if (!response.ok) {
            status("Sharing stopped on this page, but the server could not clear the last location.");
        }
    } catch (_) {
        status("Sharing stopped on this page. The server could not be reached to clear the last location.");
    }

    activeName = "";
    startButton.disabled = false;
    stopButton.disabled = true;
    nameInput.disabled = false;
    if (statusBox.textContent === "Sharing is on") {
        status("Sharing stopped.");
    } else if (!statusBox.textContent.startsWith("Sharing stopped")) {
        status("Sharing stopped on this page.");
    }
});

window.addEventListener("pagehide", () => {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
});
</script>
</body>
</html>
"""


DASHBOARD_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Family Dashboard</title>
<link rel="stylesheet"
 href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*{box-sizing:border-box}
body{margin:0;background:#081321;color:#edf7ff;font-family:Arial,sans-serif}
header{padding:22px 5%;display:flex;justify-content:space-between;
align-items:center;gap:15px;flex-wrap:wrap;border-bottom:1px solid #203449}
.brand{font-size:22px;font-weight:bold}
.brand span{color:#37dac8}
nav{display:flex;gap:17px;flex-wrap:wrap}
a{color:#47e0cf;text-decoration:none}
main{max-width:1250px;margin:auto;padding:25px}
.intro{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
h1{margin-bottom:7px}p{color:#9db2c6;line-height:1.5}
button{border:0;border-radius:9px;padding:12px 15px;background:#25d5bd;
color:#06201f;font-weight:bold;cursor:pointer}
.layout{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,1fr);
gap:18px;margin-top:20px}
.panel{background:#102235;border:1px solid #203b50;border-radius:16px;padding:18px;min-width:0}
#map{height:430px;border-radius:12px;background:#172b3c}
.member{padding:13px 0;border-bottom:1px solid #294054}
.member:last-child{border:0}
.member strong{display:block;margin-bottom:7px}
.meta{font-size:13px;color:#a8bdce;line-height:1.7;overflow-wrap:anywhere}
.pill{display:inline-block;padding:5px 8px;border-radius:20px;font-size:12px;
background:#183d3c;color:#69e6d7;margin-bottom:7px}
.stale{background:#49351f;color:#ffd18b}
.empty{color:#9db2c6;padding:18px 0}
#message{font-size:13px}
@media(max-width:800px){.layout{grid-template-columns:1fr}#map{height:340px}main{padding:17px}}
</style>
</head>
<body>
<header>
<div class="brand">⌖ Family <span>Location</span></div>
<nav><a href="/share">Share my location</a>
<a href="/logout">Log out</a></nav>
</header>
<main>
<div class="intro">
<div><h1>Family dashboard</h1>
<p>See locations that family members have chosen to share.</p></div>
<button id="refresh">Refresh locations</button>
</div>
<div class="layout">
<section class="panel">
<h2>Family map</h2>
<div id="map"></div>
<p id="message">Loading locations…</p>
</section>
<section class="panel">
<h2>Family members</h2>
<div id="people"><div class="empty">Loading…</div></div>
</section>
</div>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map("map").setView([22.5726, 88.3639], 5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const markers = new Map();
const people = document.getElementById("people");
const message = document.getElementById("message");

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    })[c]);
}

async function refreshLocations() {
    try {
        const response = await fetch("/api/locations", {cache: "no-store"});
        if (!response.ok) {
            throw new Error("Could not load locations. Please sign in again.");
        }
        const data = await response.json();
        people.replaceChildren();
        const activeNames = new Set();

        if (!data.length) {
            people.innerHTML = '<div class="empty">No locations shared yet. Family members can open Share my location to begin.</div>';
            message.textContent = "No shared locations yet.";
            markers.forEach(marker => map.removeLayer(marker));
            markers.clear();
            return;
        }

        const bounds = [];
        data.forEach(person => {
            activeNames.add(person.name);
            const age = Math.max(0, Math.floor(Date.now()/1000 - person.updated_at));
            const fresh = age <= 60;
            const ageText = age < 60 ? "just now" :
                Math.floor(age/60) + " minute(s) ago";
            const card = document.createElement("div");
            card.className = "member";
            card.innerHTML =
                '<strong>' + escapeHtml(person.name) + '</strong>' +
                '<span class="pill ' + (fresh ? '' : 'stale') + '">' +
                (fresh ? 'Recently updated' : 'Possibly outdated') + '</span>' +
                '<div class="meta">Updated: ' + escapeHtml(ageText) + '<br>' +
                'Accuracy: about ' + escapeHtml(Math.round(person.accuracy || 0)) + ' m<br>' +
                '<a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=' +
                encodeURIComponent(person.latitude) + '&mlon=' +
                encodeURIComponent(person.longitude) + '#map=16/' +
                encodeURIComponent(person.latitude) + '/' +
                encodeURIComponent(person.longitude) + '">Open map</a></div>';
            people.appendChild(card);

            const point = [person.latitude, person.longitude];
            bounds.push(point);
            const popup = '<strong>' + escapeHtml(person.name) + '</strong><br>' +
                'Updated ' + escapeHtml(ageText);
            if (markers.has(person.name)) {
                markers.get(person.name).setLatLng(point).setPopupContent(popup);
            } else {
                markers.set(person.name, L.marker(point).addTo(map).bindPopup(popup));
            }
        });

         for (const [name, marker] of markers) {
            if (!activeNames.has(name)) {
                map.removeLayer(marker);
                markers.delete(name);
            }
        }
        if (bounds.length === 1) map.setView(bounds[0], 15);
        else if (bounds.length > 1) map.fitBounds(bounds, {padding:[25,25], maxZoom:14});
        message.textContent = "Last refreshed: " + new Date().toLocaleTimeString();
    } catch (error) {
        message.textContent = error.message;
    }
}

document.getElementById("refresh").addEventListener("click", refreshLocations);
refreshLocations();
setInterval(refreshLocations, 5000);
</script>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    csrf = get_csrf_token()
    error = None

    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        if not supplied or supplied != session.get("csrf_token"):
            error = "Please refresh the page and try again."
        elif secrets.compare_digest(
            request.form.get("password", ""),
            FAMILY_PASSWORD
        ):
            session.clear()
            session["logged_in"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"))
        else:
            error = "Incorrect password. Please try again."

    return render_template_string(LOGIN_PAGE, csrf=csrf, error=error)


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method == "GET":
        return (
            '<p>To log out, submit the protected form below.</p>'
            '<form method="post">'
            '<input type="hidden" name="csrf_token" value="' +
            get_csrf_token() +
            '"><button type="submit">Log out</button></form>'
        )
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template_string(DASHBOARD_PAGE)


@app.route("/share")
@login_required
def share():
    return render_template_string(SHARE_PAGE, csrf=get_csrf_token())


@app.route("/api/location", methods=["POST"])
@login_required
def update_location():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid location data."}), 400

    if not name or len(name) > 60:
        return jsonify({"error": "Enter a valid name."}), 400
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({"error": "Coordinates are out of range."}), 400
    if not (0 <= accuracy <= 100000):
        return jsonify({"error": "Invalid accuracy."}), 400

    locations[name] = {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "updated_at": time.time()
    }
    session["sharing_name"] = name
    return jsonify({"ok": True})


@app.route("/api/location", methods=["DELETE"])
@login_required
def delete_location():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()

    if name and name == session.get("sharing_name"):
        locations.pop(name, None)
        session.pop("sharing_name", None)

    return jsonify({"ok": True})


@app.route("/api/locations")
@login_required
def get_locations():
    now = time.time()
    expired = [
        name for name, item in locations.items()
        if now - item["updated_at"] > LOCATION_MAX_AGE
    ]
    for name in expired:
        locations.pop(name, None)

    return jsonify(sorted(
        locations.values(),
        key=lambda item: item["name"].casefold()
    ))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
