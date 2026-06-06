# BP-Agro-IoT / global_management / app.py
# ─────────────────────────────────────────────────────────────
# Service : BP Agro IoT — Client & Farm Management
# Port    : 5000
# Purpose : Client & farm management, data ingestion from gateways.
#           Node/gateway assignment is handled by the QR reader app.
#
# Routes  : /api/global/client/...  — client CRUD
#           /api/global/farm/...    — farm CRUD
#           /api/global/stats       — dashboard KPIs
# ─────────────────────────────────────────────────────────────

import os
import logging
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))

# ── Register Blueprints (client + farm only) ──────────────────
from routes.farm_routes   import farm_bp
from routes.client_routes import client_bp

app.register_blueprint(farm_bp)
app.register_blueprint(client_bp)


# ── Dashboard stats endpoint ──────────────────────────────────
@app.route('/api/global/stats', methods=['GET'])
def dashboard_stats():
    """Platform-wide KPIs for the management dashboard.
    Returns totals for clients, farms, zones, active sensors,
    online gateways, and sensor readings in the last 24 h.
    Node/gateway details are NOT exposed here — those are
    handled by the QR reader assignment flow.
    """
    try:
        from routes.client_routes import get_db_connection
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM client)                         AS total_clients,
                (SELECT COUNT(*) FROM farms)                          AS total_farms,
                (SELECT COUNT(*) FROM zones)                          AS total_zones,
                (SELECT COUNT(*) FROM sensors  WHERE is_active = 1)  AS active_sensors,
                (SELECT COUNT(*) FROM gateway  WHERE status = 'online') AS online_gateways,
                (SELECT COUNT(*) FROM soildata
                 WHERE timestamp >= NOW() - INTERVAL 24 HOUR)        AS readings_24h
        """)
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({'stats': stats, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"dashboard_stats error: {e}")
        return jsonify({'error': str(e)}), 500


# ── Health / info ─────────────────────────────────────────────
@app.route('/api/global/health', methods=['GET'])
def health():
    status = {
        'status':    'healthy',
        'service':   'BP-Agro-IoT',
        'version':   '3.1.0',
        'timestamp': datetime.now().isoformat(),
        'note':      'Client & farm management only. Node/gateway assignment via QR reader.',
        'endpoints': {
            'clients': '/api/global/client',
            'farms':   '/api/global/farm',
            'stats':   '/api/global/stats',
        }
    }
    try:
        from routes.client_routes import get_db_connection
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        status['database'] = 'connected'
    except Exception as e:
        status['status']         = 'degraded'
        status['database']       = 'disconnected'
        status['database_error'] = str(e)
    return jsonify(status)


@app.route('/api/global/info', methods=['GET'])
def info():
    return jsonify({
        'service':  'BP-Agro-IoT',
        'version':  '3.1.0',
        'purpose':  'Client & farm management, data ingestion',
        'note':     'Node/gateway assignment handled by QR reader app',
        'database': 'AWS Aurora MySQL',
    })


# ── Entry point ───────────────────────────────────────────────
if __name__ == '__main__':
    port  = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    logger.info(f"BP-Agro-IoT (client+farm) starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
