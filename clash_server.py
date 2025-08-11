#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import os
import socket
from datetime import datetime, timezone, timedelta
import threading
import time

# Configuración del puerto
PORT = 8000

# Configuración API Clash of Clans
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjQ0MmM5NDI3LWRmZWUtNDUzOS05YzM3LTY0YTI4ZWQ3NWQ2YSIsImlhdCI6MTc1NDc4NzA4NCwic3ViIjoiZGV2ZWxvcGVyL2ZjNTE2YWY0LTA4YzUtYTUwYS1iNjA1LTA0NWJiN2Y2MWYxNyIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjE5MC40OC4xMTkuMTAwIl0sInR5cGUiOiJjbGllbnQifV19.wX0TqtjSP7HUxVs9cvopoFZk_5wp-fG70HOrQaF-EOBKgUUBYXySAU7GMfnOx8ivnqB3qgKv-Urb_S79dBEpQw"
API_BASE_URL = "https://api.clashofclans.com/v1"

# Cache para datos de clanes
clan_cache = {}
daily_donations_cache = {}
last_update = None

# Archivo para persistir donaciones diarias
DONATIONS_FILE = "daily_donations.json"

def save_daily_donations():
    """Guarda las donaciones diarias en archivo"""
    try:
        with open(DONATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(daily_donations_cache, f, ensure_ascii=False, indent=2)
        # Mensaje silencioso - no hacer spam en consola
        # print("💾 Donaciones diarias guardadas")
    except Exception as e:
        print(f"❌ Error guardando donaciones: {e}")

def load_daily_donations():
    """Carga las donaciones diarias desde archivo"""
    global daily_donations_cache
    try:
        if os.path.exists(DONATIONS_FILE):
            with open(DONATIONS_FILE, 'r', encoding='utf-8') as f:
                daily_donations_cache = json.load(f)
            print(f"📂 Donaciones diarias cargadas desde {DONATIONS_FILE}")
            print(f"📊 {len([k for k in daily_donations_cache.keys() if not k.endswith('_reset')])} jugadores en cache")
        else:
            print("📂 No hay archivo de donaciones previo - empezando limpio")
            daily_donations_cache = {}
    except Exception as e:
        print(f"❌ Error cargando donaciones: {e}")
        daily_donations_cache = {}

def load_clans():
    """Devuelve la lista de clanes a monitorear"""
    return {
        "22G8YL992": "req n go",
        "2QQ89Y0JG": "Nuevo Clan"  # Clan agregado con ID corregido
    }

def make_api_request(endpoint):
    """Realiza una petición a la API de Clash of Clans"""
    try:
        url = f"{API_BASE_URL}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Accept': 'application/json',
            'User-Agent': 'ClashTracker/1.0'
        }

        print(f"📡 Haciendo petición a: {endpoint}")
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                print(f"✅ Petición exitosa: {endpoint}")
                return data
            else:
                print(f"❌ Error API: Status {response.status}")
                return None

    except urllib.error.HTTPError as e:
        error_msg = ""
        try:
            error_response = e.read().decode('utf-8')
            print(f"📄 Error response body: {error_response}")
            error_detail = json.loads(error_response)
            error_msg = error_detail.get('message', 'Unknown error')
        except:
            error_msg = e.reason

        print(f"❌ HTTP Error {e.code}: {error_msg}")

        # Errores comunes de la API
        if e.code == 403:
            print("🔐 Error 403: Verifica tu API Key y que tu IP esté autorizada")
            print("💡 Tu IP debe estar registrada como: 190.48.119.100")
        elif e.code == 404:
            print(f"🔍 Error 404: Clan no encontrado - verifica el ID del clan")
        elif e.code == 429:
            print("⏰ Error 429: Límite de peticiones excedido - espera un momento")
        elif e.code == 400:
            print("⚠️ Error 400: Petición malformada - verifica el formato del clan tag")

        return None

    except urllib.error.URLError as e:
        print(f"❌ URL Error: {e.reason}")
        print("🌐 Problema de conexión - verifica tu internet")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return None

def calculate_daily_donations(clan_tag, member_tag, current_total):
    """
    Calcula donaciones diarias reales - solo suma cuando realmente donas
    """
    global daily_donations_cache
    
    # Obtener hora argentina actual
    argentina_tz = timezone(timedelta(hours=-3))
    now_argentina = datetime.now(argentina_tz)
    today_key = now_argentina.strftime('%Y-%m-%d')
    
    # Clave para este miembro
    cache_key = f"{clan_tag}_{member_tag}"
    
    # Verificar si es hora de resetear (2 AM Argentina)
    if now_argentina.hour == 2 and now_argentina.minute < 5:
        reset_key = f"{today_key}_reset"
        if daily_donations_cache.get(reset_key) != today_key:
            print(f"🌙 Reseteando donaciones diarias - 2 AM Argentina")
            # Resetear todas las donaciones diarias
            for key in list(daily_donations_cache.keys()):
                if not key.endswith('_reset'):
                    daily_donations_cache[key] = {
                        'last_total': daily_donations_cache[key].get('last_total', 0),
                        'daily_accumulated': 0,
                        'last_update': now_argentina.isoformat()
                    }
            daily_donations_cache[reset_key] = today_key
            # Guardar después del reset
            save_daily_donations()
    
    # Si no existe el registro, crearlo
    if cache_key not in daily_donations_cache:
        daily_donations_cache[cache_key] = {
            'last_total': current_total,
            'daily_accumulated': 0,
            'last_update': now_argentina.isoformat()
        }
        save_daily_donations()
        return 0
    
    # Obtener datos anteriores
    cache_data = daily_donations_cache[cache_key]
    last_total = cache_data.get('last_total', current_total)
    daily_accumulated = cache_data.get('daily_accumulated', 0)
    
    # Solo sumar si las donaciones totales aumentaron
    if current_total > last_total:
        difference = current_total - last_total
        daily_accumulated += difference
        print(f"👤 {member_tag}: +{difference} donaciones (Total día: {daily_accumulated})")
        
        # Actualizar cache
        daily_donations_cache[cache_key] = {
            'last_total': current_total,
            'daily_accumulated': daily_accumulated,
            'last_update': now_argentina.isoformat()
        }
        
        # Guardar en archivo inmediatamente
        save_daily_donations()
    
    return daily_accumulated

def get_clan_data_from_api(clan_tag):
    """Obtiene datos reales del clan desde la API de Clash of Clans"""
    global clan_cache

    # Limpiar el tag (remover # si está presente)
    clean_tag = clan_tag.replace('#', '')

    print(f"🔍 Obteniendo datos del clan #{clean_tag}...")

    try:
        # Obtener información básica del clan
        clan_info = make_api_request(f"clans/%23{clean_tag}")
        if not clan_info:
            print(f"❌ No se pudo obtener info del clan #{clean_tag}")
            return get_fallback_clan_data(clan_tag)

        # Obtener miembros del clan
        members_info = clan_info.get('memberList', [])

        # Calcular totales
        total_donations = sum(member.get('donations', 0) for member in members_info)
        total_received = sum(member.get('donationsReceived', 0) for member in members_info)

        # Procesar lista de miembros con donaciones diarias reales
        member_list = []
        for member in members_info:
            member_tag = member.get('tag', '')
            member_name = member.get('name', 'Unknown')
            current_donations = member.get('donations', 0)
            
            # Calcular donaciones diarias reales
            daily_donations = calculate_daily_donations(clean_tag, member_tag, current_donations)
            
            member_list.append({
                "tag": member_tag,
                "name": member_name,
                "donations": current_donations,
                "donationsReceived": member.get('donationsReceived', 0),
                "trophies": member.get('trophies', 0),
                "dailyDonations": daily_donations
            })

        # Buscar líder
        leader_name = "Unknown"
        for member in members_info:
            if member.get('role') == 'leader':
                leader_name = member.get('name', 'Unknown')
                break

        clan_data = {
            "name": clan_info.get('name', 'Unknown Clan'),
            "members": clan_info.get('members', 0),
            "leader": leader_name,
            "totalDonations": total_donations,
            "totalReceived": total_received,
            "memberList": member_list,
            "level": clan_info.get('clanLevel', 1),
            "points": clan_info.get('clanPoints', 0)
        }

        # Actualizar cache
        clan_cache[clan_tag] = {
            "data": clan_data,
            "timestamp": datetime.now()
        }

        print(f"✅ Datos obtenidos para {clan_data['name']}: {total_donations:,} donaciones")
        return clan_data

    except Exception as e:
        print(f"❌ Error al obtener datos del clan #{clean_tag}: {str(e)}")
        return get_fallback_clan_data(clan_tag)

def get_fallback_clan_data(clan_tag):
    """Datos de respaldo si la API falla"""
    print(f"⚠️ Usando datos de respaldo para clan #{clan_tag}")
    
    clans = load_clans()
    clan_name = clans.get(clan_tag, f"Clan #{clan_tag}")
    
    return {
        "name": clan_name,  
        "members": 1,
        "leader": "Leader Respaldo",
        "totalDonations": 0,
        "totalReceived": 0,
        "memberList": [
            {"tag": "BACKUP1", "name": "Datos de respaldo", "donations": 0, "donationsReceived": 0, "trophies": 0, "dailyDonations": 0}
        ]
    }

def get_clan_data(clan_tag):
    """Obtiene datos del clan (cache o API)"""
    global clan_cache

    # Verificar cache (válido por 2 minutos)
    if clan_tag in clan_cache:
        cache_time = clan_cache[clan_tag]["timestamp"]
        if (datetime.now() - cache_time).seconds < 120:
            print(f"📋 Usando cache para clan #{clan_tag}")
            return clan_cache[clan_tag]["data"]

    # Obtener datos frescos de la API
    return get_clan_data_from_api(clan_tag)

def process_clans_ranking():
    """Procesa y ordena los clanes por donaciones totales"""
    print("🔄 Actualizando ranking de clanes...")
    clans = load_clans()
    ranking = []

    rank = 1
    for clan_tag, clan_name in clans.items():
        clan_data = get_clan_data(clan_tag)
        ranking.append({
            "rank": rank,
            "tag": clan_tag,
            "name": clan_data["name"],
            "leader": clan_data["leader"],
            "totalDonations": clan_data["totalDonations"],
            "totalReceived": clan_data["totalReceived"],
            "members": clan_data["members"]
        })
        rank += 1

    # Ordenar por donaciones totales (descendente)
    ranking.sort(key=lambda x: x["totalDonations"], reverse=True)

    # Reajustar rankings después del ordenamiento
    for i, clan in enumerate(ranking):
        clan["rank"] = i + 1

    global last_update
    last_update = datetime.now()

    print(f"✅ Ranking actualizado - {len(ranking)} clanes procesados")
    return ranking

def auto_update_worker():
    """Hilo que actualiza automáticamente cada 2 minutos"""
    print("🤖 Iniciando actualizador automático...")

    while True:
        try:
            time.sleep(120)  # 2 minutos
            print("⏰ Ejecutando actualización automática...")

            # Limpiar cache viejo
            global clan_cache
            current_time = datetime.now()
            clan_cache = {
                tag: data for tag, data in clan_cache.items()
                if (current_time - data["timestamp"]).seconds < 300  # 5 minutos max
            }

            # Forzar actualización del ranking
            process_clans_ranking()

        except Exception as e:
            print(f"❌ Error en actualización automática: {e}")

HTML_PAGE = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOP REQ CLANS</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
        }

        .header {
            background: #1a1a1a;
            color: white;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .logo {
            font-size: 18px;
            font-weight: bold;
        }

        .logo .top { color: #ff6b35; }
        .logo .req { color: #ff1744; }
        .logo .clans { color: #ff6b35; }

        .nav {
            display: flex;
            gap: 20px;
            font-size: 14px;
        }

        .nav a {
            color: #ccc;
            text-decoration: none;
            padding: 5px 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            min-height: calc(100vh - 60px);
        }

        .main-view {
            padding: 20px;
        }

        .page-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }

        .update-info {
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        }

        .api-status {
            background: #e8f5e8;
            color: #2e7d32;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 15px;
            border-left: 4px solid #4caf50;
        }

        .clans-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }

        .clans-table th {
            background: #f8f9fa;
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            font-size: 14px;
            color: #495057;
        }

        .clans-table th:first-child {
            width: 40px;
            text-align: center;
        }

        .clans-table td {
            padding: 12px;
            border-bottom: 1px solid #f1f1f1;
            vertical-align: middle;
        }

        .clans-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .clans-table tr:hover {
            background: #e3f2fd;
            cursor: pointer;
        }

        .clan-rank {
            text-align: center;
            font-weight: bold;
            color: #666;
        }

        .clan-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .clan-badge {
            width: 32px;
            height: 32px;
            background: #6c5ce7;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
            flex-shrink: 0;
        }

        .clan-badge.your-clan {
            background: #ff6b35;
            box-shadow: 0 0 10px rgba(255, 107, 53, 0.4);
        }

        .clan-details h4 {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 2px;
            color: #333;
        }

        .clan-tag {
            font-size: 11px;
            color: #666;
            font-family: monospace;
        }

        .leader-name {
            font-weight: 500;
            color: #333;
        }

        .donations-number {
            font-weight: 600;
            color: #2e7d32;
            text-align: right;
        }

        .received-number {
            font-weight: 600;
            color: #d32f2f;
            text-align: right;
        }

        .clan-detail-view {
            display: none;
            padding: 20px;
        }

        .back-button {
            background: #6c5ce7;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-bottom: 20px;
            font-size: 14px;
        }

        .clan-header {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 20px;
        }

        .clan-name {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 8px;
        }

        .clan-stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            font-size: 14px;
            color: #666;
        }

        .tab-buttons {
            display: flex;
            margin-bottom: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            overflow: hidden;
        }

        .tab-button {
            flex: 1;
            padding: 12px 20px;
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .tab-button.active {
            background: #6c5ce7;
            color: white;
        }

        .players-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }

        .players-table th {
            background: #f8f9fa;
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            font-size: 14px;
        }

        .players-table td {
            padding: 12px;
            border-bottom: 1px solid #f1f1f1;
        }

        .players-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .player-rank {
            text-align: center;
            font-weight: bold;
            color: #666;
            width: 40px;
        }

        .player-name {
            font-weight: 500;
        }

        .auto-refresh {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #6c5ce7;
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }

        @media (max-width: 768px) {
            .nav {
                display: none;
            }

            .clans-table, .players-table {
                font-size: 12px;
            }

            .clans-table td, .clans-table th,
            .players-table td, .players-table th {
                padding: 8px 6px;
            }

            .clan-stats {
                flex-direction: column;
                gap: 10px;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <span class="top">TOP</span> <span class="req">REQ</span> <span class="clans">CLANS</span>
        </div>
        <nav class="nav">
            <a href="#">Level</a>
            <a href="#" style="color: white;">Clans ▼</a>
            <a href="#">Players ▼</a>
            <a href="#">Contact</a>
        </nav>
    </header>

    <div class="container">
        <div class="main-view" id="mainView">
            <h1 class="page-title">Top Req Clans - Current season</h1>
            <div class="api-status">🟢 Conectado a la API oficial de Clash of Clans</div>
            <p class="update-info">Clan data is updated 24/7! (Last updated: <span id="lastUpdate">Loading...</span>)</p>

            <table class="clans-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Clan</th>
                        <th>Leader</th>
                        <th style="text-align: right;">Total Donate</th>
                        <th style="text-align: right;">Received ▲</th>
                    </tr>
                </thead>
                <tbody id="clansTableBody">
                    <!-- Los clanes se cargarán aquí -->
                </tbody>
            </table>
        </div>

        <div class="clan-detail-view" id="clanDetailView">
            <button class="back-button" onclick="showMainView()">← Back to Clans</button>

            <div class="clan-header">
                <div class="clan-name" id="detailClanName">Clan Name</div>
                <div class="clan-stats">
                    <span>Leader: <span id="detailLeader">Leader</span></span>
                    <span>Members: <span id="detailMembers">0</span></span>
                    <span>Total Donations: <span id="detailTotalDonations">0</span></span>
                </div>
            </div>

            <div class="tab-buttons">
                <button class="tab-button active" onclick="showPlayersTab('total')" id="totalDonationsBtn">
                    Donaciones Temporada
                </button>
                <button class="tab-button" onclick="showPlayersTab('daily')" id="dailyDonationsBtn">
                    Donaciones Hoy
                </button>
            </div>

            <table class="players-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Player</th>
                        <th style="text-align: right;">Donaciones</th>
                        <th style="text-align: right;">Recibidas</th>
                        <th style="text-align: right;">Trofeos</th>
                    </tr>
                </thead>
                <tbody id="playersTableBody">
                    <!-- Los jugadores se cargarán aquí -->
                </tbody>
            </table>
        </div>
    </div>

    <div class="auto-refresh" id="autoRefresh">
        🔄 Next update in: <span id="countdown">120</span>s
    </div>

    <script>
        var currentData = {};
        var currentView = 'total';
        var selectedClanTag = '';
        var refreshInterval;
        var countdownInterval;
        var secondsLeft = 120;

        function formatNumber(num) {
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }

        function updateLastUpdateTime() {
            var now = new Date();
            document.getElementById('lastUpdate').textContent = 'hace 1 seg';
        }

        function startCountdown() {
            countdownInterval = setInterval(function() {
                secondsLeft--;
                document.getElementById('countdown').textContent = secondsLeft;

                if (secondsLeft <= 0) {
                    secondsLeft = 120;
                }
            }, 1000);
        }

        function loadClansRanking() {
            fetch('/api/ranking')
            .then(function(response) { return response.json(); })
            .then(function(ranking) {
                var tbody = document.getElementById('clansTableBody');
                tbody.innerHTML = '';

                ranking.forEach(function(clan) {
                    var row = document.createElement('tr');
                    row.onclick = function() { showClanDetail(clan.tag); };

                    var clanInitial = clan.name.charAt(0).toUpperCase();
                    var badgeClass = 'clan-badge your-clan';

                    row.innerHTML = 
                        '<td class="clan-rank">' + clan.rank + '.</td>' +
                        '<td class="clan-info">' +
                            '<div class="' + badgeClass + '">' + clanInitial + '</div>' +
                            '<div class="clan-details">' +
                                '<h4>' + clan.name + '</h4>' +
                                '<div class="clan-tag">#' + clan.tag + '</div>' +
                            '</div>' +
                        '</td>' +
                        '<td class="leader-name">' + clan.leader + '</td>' +
                        '<td class="donations-number">' + formatNumber(clan.totalDonations) + '</td>' +
                        '<td class="received-number">' + formatNumber(clan.totalReceived) + '</td>';

                    tbody.appendChild(row);
                });

                updateLastUpdateTime();
                secondsLeft = 120;
            })
            .catch(function(error) {
                console.error('Error loading clans:', error);
            });
        }

        function showClanDetail(clanTag) {
            selectedClanTag = clanTag;

            fetch('/api/clan/' + encodeURIComponent(clanTag))
            .then(function(response) { return response.json(); })
            .then(function(data) {
                currentData = data;

                document.getElementById('mainView').style.display = 'none';
                document.getElementById('clanDetailView').style.display = 'block';

                document.getElementById('detailClanName').textContent = data.name;
                document.getElementById('detailLeader').textContent = data.leader;
                document.getElementById('detailMembers').textContent = data.members;
                document.getElementById('detailTotalDonations').textContent = formatNumber(data.totalDonations);

                showPlayersTab('total');
            })
            .catch(function(error) {
                console.error('Error loading clan details:', error);
            });
        }

        function showMainView() {
            document.getElementById('mainView').style.display = 'block';
            document.getElementById('clanDetailView').style.display = 'none';
            selectedClanTag = '';
        }

        function showPlayersTab(tabType) {
            currentView = tabType;

            document.getElementById('totalDonationsBtn').classList.remove('active');
            document.getElementById('dailyDonationsBtn').classList.remove('active');
            document.getElementById(tabType === 'total' ? 'totalDonationsBtn' : 'dailyDonationsBtn').classList.add('active');

            if (!currentData.memberList) {
                return;
            }

            var players = currentData.memberList.slice();

            players.sort(function(a, b) {
                var aValue = tabType === 'total' ? (a.donations || 0) : (a.dailyDonations || 0);
                var bValue = tabType === 'total' ? (b.donations || 0) : (b.dailyDonations || 0);
                return bValue - aValue;
            });

            var tbody = document.getElementById('playersTableBody');
            tbody.innerHTML = '';

            players.forEach(function(player, index) {
                var donations = tabType === 'total' ? (player.donations || 0) : (player.dailyDonations || 0);

                var row = document.createElement('tr');
                row.innerHTML = 
                    '<td class="player-rank">' + (index + 1) + '.</td>' +
                    '<td class="player-name">' + player.name + '</td>' +
                    '<td style="text-align: right; font-weight: 600; color: #2e7d32;">' + formatNumber(donations) + '</td>' +
                    '<td style="text-align: right; font-weight: 600; color: #d32f2f;">' + formatNumber(player.donationsReceived) + '</td>' +
                    '<td style="text-align: right;">' + formatNumber(player.trophies) + '</td>';

                tbody.appendChild(row);
            });
        }

        function startAutoRefresh() {
            refreshInterval = setInterval(function() {
                if (document.getElementById('mainView').style.display !== 'none') {
                    loadClansRanking();
                } else if (selectedClanTag) {
                    showClanDetail(selectedClanTag);
                }
            }, 120000); // 2 minutos
        }

        window.onload = function() { 
            loadClansRanking();
            startAutoRefresh();
            startCountdown();
        };

        window.onbeforeunload = function() {
            if (refreshInterval) clearInterval(refreshInterval);
            if (countdownInterval) clearInterval(countdownInterval);
        };
    </script>
</body>
</html>'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))

        elif self.path == "/api/ranking":
            try:
                ranking = process_clans_ranking()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(ranking).encode('utf-8'))
            except Exception as e:
                print(f"❌ Error en /api/ranking: {e}")
                self.send_response(500)
                self.end_headers()

        elif self.path.startswith("/api/clan/"):
            try:
                clan_tag = urllib.parse.unquote(self.path.split("/")[-1])
                clan_data = get_clan_data(clan_tag)

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(clan_data).encode('utf-8'))
            except Exception as e:
                print(f"❌ Error en /api/clan: {e}")
                self.send_response(500)
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silencia los logs del servidor HTTP
        pass

def main():
    print("🚀 Iniciando TOP REQ CLANS Server...")
    print(f"📱 Abre tu navegador en: http://localhost:{PORT}")
    print("🔗 Intentando conectar a la API oficial de Clash of Clans")
    print(f"🏠 Clanes configurados:")
    clans = load_clans()
    for clan_tag, clan_name in clans.items():
        print(f"   • #{clan_tag} ({clan_name})")
    print(f"🔑 API Key configurada: ...{API_KEY[-10:]}")
    print("⏰ Auto-refresh cada 2 minutos")
    print("🌙 Reset donaciones diarias: 2:00 AM Argentina")
    print("💾 Donaciones diarias se guardan automáticamente")
    print("🔄 Presiona Ctrl+C para detener el servidor")
    print("-" * 50)

    # Cargar donaciones diarias guardadas
    print("📂 Cargando donaciones diarias...")
    load_daily_donations()
    print("-" * 50)

    # Test inicial de la API con ambos clanes
    print("🧪 Probando conexión con la API...")
    
    clans = load_clans()
    for clan_tag, clan_name in clans.items():
        print(f"🔍 Probando clan #{clan_tag} ({clan_name})...")
        test_result = make_api_request(f"clans/%23{clan_tag}")
        if test_result:
            print(f"✅ ¡API funcionando correctamente con {clan_name}!")
        else:
            print(f"❌ Error con el clan #{clan_tag} - usando datos de respaldo")
    
    print("-" * 50)

    # Iniciar hilo de actualización automática
    update_thread = threading.Thread(target=auto_update_worker, daemon=True)
    update_thread.start()

    # Carga inicial
    print("🔄 Cargando datos iniciales...")
    try:
        initial_ranking = process_clans_ranking()
        print(f"✅ {len(initial_ranking)} clanes cargados exitosamente")
    except Exception as e:
        print(f"⚠️ Error en carga inicial: {e}")

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print("✅ ¡Servidor funcionando!")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n💾 Guardando donaciones antes de cerrar...")
        save_daily_donations()
        print("👋 Servidor detenido")
    except Exception as e:
        print(f"❌ Error: {e}")
        # Guardar datos antes de salir por error
        save_daily_donations()

if __name__ == "__main__":
    main()


