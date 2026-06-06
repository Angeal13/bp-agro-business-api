# BP-Agro-Cloud/global_management/routes/client_routes.py
# Client Management API Routes

from flask import Blueprint, request, jsonify
from datetime import datetime
import mysql.connector
import logging
import random
import string

from ..config.aurora_config import get_db_config

logger = logging.getLogger(__name__)

client_bp = Blueprint('client', __name__, url_prefix='/api/global/client')

def get_db_connection():
    """Get database connection"""
    db_config = get_db_config()
    return mysql.connector.connect(**db_config)

def generate_client_id() -> str:
    """Generate unique client ID"""
    prefix = 'CLI'
    random_digits = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{random_digits}"

@client_bp.route('/create', methods=['POST'])
def create_client():
    """
    Create a new client
    """
    try:
        data = request.get_json()
        
        if 'client_name' not in data:
            return jsonify({'error': 'Missing client_name'}), 400
        
        client_id = generate_client_id()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if client already exists (case-insensitive)
            cursor.execute(
                "SELECT client_id FROM client WHERE LOWER(client_name) = LOWER(%s)",
                (data['client_name'],)
            )
            if cursor.fetchone():
                return jsonify({'error': 'Client already exists'}), 409
            
            cursor.execute("""
                INSERT INTO client (
                    client_id, client_name, email, whatsapp
                )
                VALUES (%s, %s, %s, %s)
            """, (
                client_id,
                data['client_name'],
                data.get('email', ''),
                data.get('whatsapp', '')
            ))
            
            conn.commit()
            
            logger.info(f"Client created: {client_id} - {data['client_name']}")
            
            return jsonify({
                'success': True,
                'client_id': client_id,
                'client_name': data['client_name']
            })
            
        except mysql.connector.Error as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Create client error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@client_bp.route('/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get client details with farm summary"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                c.*,
                COUNT(DISTINCT f.farm_id) as farm_count,
                COUNT(DISTINCT z.zone_id) as zone_count,
                COUNT(DISTINCT s.machine_id) as sensor_count
            FROM client c
            LEFT JOIN farms f ON c.client_id = f.client_id
            LEFT JOIN zones z ON f.farm_id = z.farm_id
            LEFT JOIN sensors s ON f.farm_id = s.farm_id
            WHERE c.client_id = %s
            GROUP BY c.client_id
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get recent farms
        cursor.execute("""
            SELECT farm_id, farm_name, created_at 
            FROM farms 
            WHERE client_id = %s 
            ORDER BY created_at DESC 
            LIMIT 5
        """, (client_id,))
        
        recent_farms = cursor.fetchall()
        
        return jsonify({
            'client': client,
            'recent_farms': recent_farms
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@client_bp.route('/<client_id>', methods=['PUT'])
def update_client(client_id):
    """
    Update client information
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if client exists
            cursor.execute("SELECT client_id FROM client WHERE client_id = %s", (client_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Client not found'}), 404
            
            # Build update query dynamically
            update_fields = []
            update_values = []
            
            if 'client_name' in data and data['client_name']:
                update_fields.append("client_name = %s")
                update_values.append(data['client_name'])
            
            if 'email' in data:
                update_fields.append("email = %s")
                update_values.append(data['email'])
            
            if 'whatsapp' in data:
                update_fields.append("whatsapp = %s")
                update_values.append(data['whatsapp'])
            
            if not update_fields:
                return jsonify({'error': 'No valid fields to update'}), 400
            
            update_values.append(client_id)
            
            query = f"UPDATE client SET {', '.join(update_fields)} WHERE client_id = %s"
            cursor.execute(query, update_values)
            
            conn.commit()
            
            logger.info(f"Client updated: {client_id}")
            
            return jsonify({
                'success': True,
                'client_id': client_id,
                'updated_fields': [field.split()[0] for field in update_fields]
            })
            
        except mysql.connector.Error as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Update client error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@client_bp.route('/<client_id>', methods=['DELETE'])
def delete_client(client_id):
    """
    Delete a client and all associated data
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if client exists
        cursor.execute("SELECT client_name FROM client WHERE client_id = %s", (client_id,))
        client = cursor.fetchone()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        client_name = client[0]
        
        # Get all farm IDs for this client
        cursor.execute("SELECT farm_id FROM farms WHERE client_id = %s", (client_id,))
        farm_ids = [row[0] for row in cursor.fetchall()]
        
        # Count affected records before deletion
        farms_count = len(farm_ids)
        
        sensors_unassigned = 0
        zones_deleted = 0
        
        if farm_ids:
            # Unassign all sensors from these farms
            placeholders = ','.join(['%s'] * len(farm_ids))
            cursor.execute(
                f"UPDATE sensors SET farm_id = NULL, zone_code = NULL WHERE farm_id IN ({placeholders})",
                farm_ids
            )
            sensors_unassigned = cursor.rowcount
            
            # Delete all zones from these farms
            cursor.execute(
                f"DELETE FROM zones WHERE farm_id IN ({placeholders})",
                farm_ids
            )
            zones_deleted = cursor.rowcount
        
        # Delete all farms of this client
        cursor.execute("DELETE FROM farms WHERE client_id = %s", (client_id,))
        farms_deleted = cursor.rowcount
        
        # Delete the client itself
        cursor.execute("DELETE FROM client WHERE client_id = %s", (client_id,))
        client_deleted = cursor.rowcount
        
        conn.commit()
        
        logger.warning(f"Client deleted: {client_id} - {client_name}")
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'client_name': client_name,
            'summary': {
                'farms_deleted': farms_deleted,
                'zones_deleted': zones_deleted,
                'sensors_unassigned': sensors_unassigned
            }
        })
        
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@client_bp.route('/list', methods=['GET'])
def list_clients():
    """List all clients with summary statistics"""
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                c.*,
                COUNT(DISTINCT f.farm_id) as farm_count,
                COUNT(DISTINCT z.zone_id) as zone_count,
                COUNT(DISTINCT s.machine_id) as sensor_count,
                COUNT(DISTINCT CASE WHEN s.is_active = 1 THEN s.machine_id END) as active_sensors,
                MAX(f.created_at) as last_farm_created
            FROM client c
            LEFT JOIN farms f ON c.client_id = f.client_id
            LEFT JOIN zones z ON f.farm_id = z.farm_id
            LEFT JOIN sensors s ON f.farm_id = s.farm_id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (c.client_name LIKE %s OR c.email LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += """
            GROUP BY c.client_id
            ORDER BY c.client_name
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        clients = cursor.fetchall()
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) as total FROM client"
        if search:
            count_query += " WHERE client_name LIKE %s OR email LIKE %s"
            count_params = [f"%{search}%", f"%{search}%"]
            cursor.execute(count_query, count_params)
        else:
            cursor.execute(count_query)
        
        total = cursor.fetchone()['total']
        
        return jsonify({
            'clients': clients,
            'pagination': {
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@client_bp.route('/<client_id>/farms', methods=['GET'])
def get_client_farms(client_id):
    """Get all farms for a client"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                f.*,
                COUNT(DISTINCT z.zone_id) as zone_count,
                COUNT(DISTINCT s.machine_id) as sensor_count,
                (SELECT COUNT(*) FROM gateway WHERE farm_id = f.farm_id) as gateway_count
            FROM farms f
            LEFT JOIN zones z ON f.farm_id = z.farm_id
            LEFT JOIN sensors s ON f.farm_id = s.farm_id
            WHERE f.client_id = %s
            GROUP BY f.farm_id
            ORDER BY f.farm_name
        """, (client_id,))
        
        farms = cursor.fetchall()
        
        return jsonify({'farms': farms})
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@client_bp.route('/<client_id>/stats', methods=['GET'])
def get_client_stats(client_id):
    """Get detailed statistics for a client"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if client exists
        cursor.execute("SELECT client_name FROM client WHERE client_id = %s", (client_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Client not found'}), 404
        
        # Overall statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT f.farm_id) as total_farms,
                COUNT(DISTINCT z.zone_id) as total_zones,
                COUNT(DISTINCT s.machine_id) as total_sensors,
                COUNT(DISTINCT CASE WHEN s.is_active = 1 THEN s.machine_id END) as active_sensors,
                COUNT(DISTINCT g.gateway_id) as gateways
            FROM client c
            LEFT JOIN farms f ON c.client_id = f.client_id
            LEFT JOIN zones z ON f.farm_id = z.farm_id
            LEFT JOIN sensors s ON f.farm_id = s.farm_id
            LEFT JOIN gateway g ON f.farm_id = g.farm_id
            WHERE c.client_id = %s
        """, (client_id,))
        
        stats = cursor.fetchone()
        
        # Recent activity
        cursor.execute("""
            SELECT 
                'sensor_readings' as type,
                COUNT(*) as count,
                MAX(timestamp) as last_activity
            FROM soildata sd
            JOIN sensors s ON sd.machine_id = s.machine_id
            JOIN farms f ON s.farm_id = f.farm_id
            WHERE f.client_id = %s
            UNION ALL
            SELECT 
                'gateway_heartbeats',
                COUNT(*),
                MAX(last_heartbeat)
            FROM gateway g
            JOIN farms f ON g.farm_id = f.farm_id
            WHERE f.client_id = %s
            GROUP BY type
        """, (client_id, client_id))
        
        activity = cursor.fetchall()
        
        # Farm distribution by size
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN farm_length * farm_width <= 1000 THEN 'Small (<1000m²)'
                    WHEN farm_length * farm_width <= 10000 THEN 'Medium (1000-10,000m²)'
                    ELSE 'Large (>10,000m²)'
                END as size_category,
                COUNT(*) as farm_count,
                AVG(farm_length * farm_width) as avg_area
            FROM farms
            WHERE client_id = %s
            GROUP BY size_category
        """, (client_id,))
        
        size_distribution = cursor.fetchall()
        
        return jsonify({
            'stats': stats,
            'activity': activity,
            'size_distribution': size_distribution
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@client_bp.route('/health', methods=['GET'])
def client_api_health():
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
            'service': 'client_api',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500