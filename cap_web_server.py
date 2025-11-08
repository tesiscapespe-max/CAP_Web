from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import requests  # para geocodificar nombres de lugares en coordenadas

app = Flask(__name__)

# Lista en memoria donde se acumulan las alertas
alerts = []


# ----------------- Geocodificación (texto -> lat/lng) -----------------
def geocode_place(place_text):
    """
    Usa el servicio Nominatim (OpenStreetMap) para convertir
    un texto de lugar en coordenadas (lat, lng).
    Ejemplo: 'La Gasca, Quito' -> (-0.189, -78.507)
    """
    if not place_text:
        return None, None

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_text,
        "format": "json",
        "limit": 1,
    }
    headers = {
        # IMPORTANTE: pon un correo tuyo para respetar la política de Nominatim
        "User-Agent": "TESIS-CAP-ESPE/1.0 (tesiscapespe@gmail.com)"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                return lat, lng
    except Exception as e:
        print("Error geocodificando lugar:", place_text, e)

    return None, None


# ----------------- Plantilla HTML con Leaflet + lista -----------------
HTML_PAGE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>ESPE - Sistema de Alertas CAP</title>
  <meta http-equiv="refresh" content="20">
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    body { font-family: Arial, sans-serif; background: #f2f2f2; margin: 0; padding: 0; }
    header {
      background: linear-gradient(90deg, #1b5e20, #2e7d32);
      color: #fff;
      padding: 15px 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    header h1 { margin: 0; font-size: 22px; }
    header h2 { margin: 4px 0 0 0; font-size: 14px; font-weight: normal; opacity: 0.9; }

    .container { max-width: 1100px; margin: 15px auto 25px auto; padding: 0 10px; }
    .flex-row { display: flex; flex-wrap: wrap; gap: 15px; }
    .left, .right { box-sizing: border-box; }
    .left { flex: 1 1 55%; min-width: 320px; }
    .right { flex: 1 1 40%; min-width: 280px; }

    .info-bar {
      background: #e8f5e9;
      border-left: 4px solid #2e7d32;
      padding: 8px 10px;
      font-size: 13px;
      color: #2e7d32;
      border-radius: 4px;
      margin-bottom: 10px;
    }

    /* Estilo para el contenedor con scroll de alertas */
    .alerts-container {
      max-height: 400px;  /* Limita la altura del contenedor */
      overflow-y: auto;   /* Activa el scroll vertical */
      padding-right: 15px; /* Espacio para la barra de desplazamiento */
    }

    .legend {
      background: #ffffff;
      border-radius: 6px;
      padding: 6px 8px;
      font-size: 12px;
      color: #333;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      margin-bottom: 8px;
      display: inline-block;
    }
    .legend-item {
      margin-right: 10px;
      display: inline-flex;
      align-items: center;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 4px;
    }
    .dot-danger { background: #d32f2f; }
    .dot-safe { background: #2e7d32; }

    #map {
      width: 100%;
      height: 350px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.15);
      margin-bottom: 12px;
      background: #eee;
    }

    .alert-card {
      background: #ffffff;
      margin: 8px 0;
      padding: 10px 15px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.15);
      border-left: 6px solid #9e9e9e;
    }
    .severity-extrema { border-left-color: #b71c1c; }
    .severity-grave   { border-left-color: #e65100; }
    .severity-moderada{ border-left-color: #fbc02d; }
    .severity-leve    { border-left-color: #2e7d32; }

    .meta { font-size: 12px; color: #555; margin-bottom: 4px; }
    .title { font-weight: bold; font-size: 15px; margin-bottom: 4px; }
    .desc { font-size: 13px; margin-bottom: 4px; }
    .tags { font-size: 12px; color: #333; }
    .badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      margin-right: 5px;
      color: #fff;
    }
    .badge-urgencia { background: #1565c0; }
    .badge-extrema { background: #b71c1c; }
    .badge-grave { background: #e65100; }
    .badge-moderada { background: #fbc02d; color: #000; }
    .badge-leve { background: #2e7d32; }

    .empty { font-size: 13px; color: #777; margin-top: 10px; }

    /* Sección adicional: Mochila de emergencia + Resumen del sistema */
    .extra-section {
      max-width: 1100px;
      margin: 0 auto 25px auto;
      padding: 0 10px;
    }
    .extra-row {
      display: flex;
      flex-wrap: wrap;
      gap: 15px;
    }
    .extra-left, .extra-right {
      box-sizing: border-box;
      flex: 1 1 50%;
      min-width: 280px;
    }
    .card-box {
      background: #ffffff;
      padding: 12px 15px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.15);
      font-size: 13px;
    }
    .card-box h3 {
      margin-top: 0;
      margin-bottom: 6px;
      color: #2e7d32;
      font-size: 15px;
    }
    .card-box ul {
      margin: 4px 0 0 16px;
      padding: 0;
    }
    .card-box li { margin-bottom: 3px; }

    footer {
      text-align: center;
      font-size: 11px;
      color: #777;
      margin-bottom: 10px;
    }
  </style>
</head>
<body>
  <header>
    <h1>ESPE - Sistema de Mensajería CAP sobre SDR</h1>
    <h2>Visualización geográfica de alertas y zonas seguras (Leaflet + OpenStreetMap)</h2>
  </header>

  <div class="container">
    <div class="info-bar">
      Representación de mensajes CAP recibidos desde la plataforma SDR.
      <strong>Rojo:</strong> zona en peligro. <strong>Verde:</strong> zona segura o punto de encuentro.
    </div>

    <div class="flex-row">
      <div class="left">
        <div class="legend">
          <span class="legend-item">
            <span class="dot dot-danger"></span> Zona en peligro
          </span>
          <span class="legend-item">
            <span class="dot dot-safe"></span> Zona segura / punto de encuentro
          </span>
        </div>
        <div id="map"></div>
      </div>
      <div class="right">
        <div class="alerts-container">
          {% if alerts %}
            {% for a in alerts|reverse %}
              <div class="alert-card severity-{{ a['severity_es']|lower }}">
                <div class="meta">
                  {{ a['timestamp'] }} | <strong>Área:</strong> {{ a['area'] }}
                </div>
                <div class="title">{{ a['headline'] }}</div>
                <div class="desc">{{ a['description'] }}</div>
                <div class="tags">
                  <span class="badge badge-urgencia">Urgencia: {{ a['urgency_es'] }}</span>
                  <span class="badge badge-{{ a['severity_es']|lower }}">
                    Severidad: {{ a['severity_es'] }}
                  </span>
                </div>
              </div>
            {% endfor %}
          {% else %}
            <div class="empty">
              (No hay alertas recibidas por el momento. El mapa se actualizará cuando llegue un nuevo mensaje CAP.)
            </div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>

  <footer>
    Proyecto de titulación - ESPE | Sistema de transmisión y recepción de mensajes CAP sobre plataformas SDR
  </footer>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>
    const alerts = {{ alerts | tojson }};
    let lastAlert = alerts.length > 0 ? alerts[alerts.length - 1] : null;

    function initMapLeaflet() {
      let center = [-1.0, -78.5];
      let zoom = 6;

      if (lastAlert && lastAlert.lat && lastAlert.lng) {
        center = [lastAlert.lat, lastAlert.lng];
        zoom = 12;
      }

      const map = L.map('map').setView(center, zoom);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

      if (lastAlert && lastAlert.lat && lastAlert.lng) {
        L.circle([lastAlert.lat, lastAlert.lng], {
          radius: 600,
          color: '#b71c1c',
          weight: 2,
          fillColor: 'rgba(211, 47, 47, 0.25)',
          fillOpacity: 0.25
        }).addTo(map).bindPopup(lastAlert.headline || "Zona en peligro");
      }

      if (lastAlert && lastAlert.safe_places) {
        lastAlert.safe_places.forEach(p => {
          if (p.lat && p.lng) {
            L.circle([p.lat, p.lng], {
              radius: 400,
              color: '#1b5e20',
              weight: 2,
              fillColor: 'rgba(46, 125, 50, 0.25)',
              fillOpacity: 0.25
            }).addTo(map).bindPopup(p.name || "Zona segura");
          }
        });
      }
    }

    document.addEventListener("DOMContentLoaded", initMapLeaflet);
  </script>
</body>
</html>
"""



# ----------------- Rutas Flask -----------------
@app.route("/")
def index():
    return render_template_string(HTML_PAGE, alerts=alerts)


@app.route("/api/alert", methods=["POST"])
def api_alert():
    data = request.get_json(force=True)

    # Marca de tiempo
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1) Geocodificar zona en peligro usando 'area'
    area_text = data.get("area", "")
    danger_lat, danger_lng = geocode_place(area_text + ", Ecuador" if area_text else "")
    data["lat"] = danger_lat
    data["lng"] = danger_lng

    # 2) Geocodificar zona segura buscando texto "zona segura" en la descripción
    desc = data.get("description", "")
    safe_places = []

    lower = desc.lower()
    idx = lower.find("zona segura")
    if idx != -1:
        # texto que viene después de "zona segura"
        safe_part = desc[idx + len("zona segura"):].strip(" :.-")
        # Cortar en punto (.) para evitar texto extra
        safe_part = safe_part.split(".")[0]
        # Puedes dejar la coma si quieres incluir ciudad, o cortarla:
        # safe_part = safe_part.split(",")[0] if safe_part else safe_part

        if safe_part:
            safe_query = safe_part + ", Ecuador"
            safe_lat, safe_lng = geocode_place(safe_query)
            if safe_lat and safe_lng:
                safe_places.append({
                    "name": safe_part,
                    "lat": safe_lat,
                    "lng": safe_lng
                })

    data["safe_places"] = safe_places

    alerts.append(data)
    return jsonify({"status": "ok", "count": len(alerts)})


if __name__ == "__main__":
    # Localmente corre en http://localhost:5000
    app.run(host="0.0.0.0", port=5000, debug=False)

