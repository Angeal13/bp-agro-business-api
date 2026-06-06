# BP-Agro-Cloud/global_management/routes/farm_routes.py
# Farm Management API Routes

from flask import Blueprint, request, jsonify
from datetime import datetime
import mysql.connector
import logging
import random
import string

from ..config.aurora_config import get_db_config

logger = logging.getLogger(__name__)

farm_bp = Blueprint('farm', __name__, url_prefix='/api/global/farm')

def get_db_connection():
    """Get database connection"""
    db_config = get_db_config()
    return mysql.connector.connect(**db_config)

def generate_farm_id() -> str:
    """Generate unique farm ID"""
    prefix = 'FARM'
    random_digits = ''.join(random.choices(string.digits, k=5))
    return f"{prefix}{random_digits}"

@farm_bp.route('/create', methods=['POST'])
def create_farm():
    """
    Create a new farm
    """
    try:
        data = request.get_json()
        
        if 'client_id' not in data or 'farm_name' not in data:
            return jsonify({'error': 'Missing client_id or farm_name'}), 400
        
        farm_id = generate_farm_id()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT client_id FROM client WHERE client_id = %s", (data['client_id'],))
            if not cursor.fetchone():
                return jsonify({'error': 'Client not found'}), 404
            
            cursor.execute("""
                INSERT INTO farms (
                    farm_id, client_id, farm_name, emails, whatsapps,
                    farm_length, farm_width
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                farm_id,
                data['client_id'],
                data['farm_name'],
                data.get('emails', ''),
                data.get('whatsapps', ''),
                float(data.get('farm_length', 0)),
                float(data.get('farm_width', 0))
            ))
            
            conn.commit()
            
            logger.info(f"Farm created: {farm_id}")
            
            return jsonify({
                'success': True,
                'farm_id': farm_id,
                'farm_name': data['farm_name']
            })
            
        except mysql.connector.Error as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Create farm error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@farm_bp.route('/<farm_id>', methods=['GET'])
def get_farm(farm_id):
    """Get farm details"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                f.*,
                c.client_name
            FROM farms f
            JOIN client c ON f.client_id = c.client_id
            WHERE f.farm_id = %s
        """, (farm_id,))
        
        farm = cursor.fetchone()
        
        if not farm:
            return jsonify({'error': 'Farm not found'}), 404
        
        cursor.execute("""
            SELECT zone_code, crop 
            FROM zones 
            WHERE farm_id = %s 
            ORDER BY zone_code
        """, (farm_id,))
        
        zones = cursor.fetchall()
        
        cursor.execute("""
            SELECT gateway_id, local_ip, status 
            FROM gateway 
            WHERE farm_id = %s
        """, (farm_id,))
        
        gateways = cursor.fetchall()
        
        return jsonify({
            'farm': farm,
            'zones': zones,
            'gateways': gateways
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@farm_bp.route('/list', methods=['GET'])
def list_farms():
    """List all farms"""
    client_id = request.args.get('client_id')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                f.*,
                c.client_name
            FROM farms f
            JOIN client c ON f.client_id = c.client_id
            WHERE 1=1
        """
        params = []
        
        if client_id:
            query += " AND f.client_id = %s"
            params.append(client_id)
        
        query += " ORDER BY f.farm_name LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        farms = cursor.fetchall()
        
        return jsonify({'farms': farms})
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@farm_bp.route('/<farm_id>/zones', methods=['GET'])
def get_farm_zones(farm_id):
    """Get all zones for a farm"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM zones 
            WHERE farm_id = %s
            ORDER BY zone_code
        """, (farm_id,))
        
        zones = cursor.fetchall()
        
        return jsonify({'zones': zones})
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@farm_bp.route('/<farm_id>/zones/create', methods=['POST'])
def create_zone(farm_id):
    """
    Create a new zone
    """
    try:
        data = request.get_json()
        
        if 'zone_code' not in data:
            return jsonify({'error': 'Missing zone_code'}), 400
        
        zone_code = data['zone_code']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT farm_id FROM farms WHERE farm_id = %s", (farm_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Farm not found'}), 404
            
            cursor.execute("""
                INSERT INTO zones (farm_id, zone_code, crop)
                VALUES (%s, %s, %s)
            """, (farm_id, zone_code, data.get('crop', '?')))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'farm_id': farm_id,
                'zone_code': zone_code
            })
            
        except mysql.connector.Error as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Create zone error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@farm_bp.route('/<farm_id>/sensors', methods=['GET'])
def get_farm_sensors(farm_id):
    """Get all sensors for a farm"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                s.*,
                (SELECT COUNT(*) FROM soildata WHERE machine_id = s.machine_id) as total_readings
            FROM sensors s
            WHERE s.farm_id = %s
            ORDER BY s.zone_code, s.machine_id
        """, (farm_id,))
        
        sensors = cursor.fetchall()
        
        return jsonify({'sensors': sensors})
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@farm_bp.route('/health', methods=['GET'])
def farm_api_health():
    """Health check"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'service': 'farm_api',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500