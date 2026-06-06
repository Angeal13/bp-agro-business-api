# BP-Agro-Cloud/global_api/config/aurora_config.py
# Aurora Database Configuration for AWS Global API

import os
from typing import Dict, Any
import json
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)

class AuroraConfig:
    """AWS Aurora Configuration Manager with Secrets Manager integration"""
    
    # Development defaults (overridden by environment/secrets)
    DEFAULT_CONFIG = {
        'host': os.getenv('AURORA_HOST', ''),
        'port': int(os.getenv('AURORA_PORT', '3306')),
        'user': os.getenv('AURORA_USER', ''),
        'password': os.getenv('AURORA_PASSWORD', ''),
        'database': os.getenv('AURORA_DATABASE', ''),
        
        # Connection pooling
        'pool_name': 'global_api_pool',
        'pool_size': 20,
        'pool_reset_session': True,
        'autocommit': True,
        
        # Timeouts
        'connect_timeout': 10,
        'read_timeout': 30,
        'write_timeout': 30,
        
        # SSL/TLS (required for Aurora)
        'ssl_ca': '/etc/ssl/certs/rds-combined-ca-bundle.pem',
        'ssl_verify_cert': True,
        
        # Retry configuration
        'max_retries': 3,
        'retry_delay': 1,
        
        # Performance
        'use_pure': True,
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci',
    }
    
    @classmethod
    def load_from_secrets_manager(cls, secret_name: str = None) -> Dict[str, Any]:
        """
        Load database credentials from AWS Secrets Manager
        """
        if secret_name is None:
            secret_name = os.getenv('SECRETS_MANAGER_SECRET', '')
        
        config = cls.DEFAULT_CONFIG.copy()
        
        try:
            session = boto3.session.Session()
            client = session.client(service_name='secretsmanager')
            
            logger.info(f"Fetching database secret: {secret_name}")
            
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            
            if 'SecretString' in get_secret_value_response:
                secret = json.loads(get_secret_value_response['SecretString'])
                
                config.update({
                    'host': secret.get('host', config['host']),
                    'port': int(secret.get('port', config['port'])),
                    'user': secret.get('username', config['user']),
                    'password': secret.get('password', config['password']),
                    'database': secret.get('dbname', config['database']),
                })
                
                logger.info("Credentials loaded from Secrets Manager")
                
        except NoCredentialsError:
            logger.warning("AWS credentials not found")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Secret {secret_name} not found")
            else:
                logger.error(f"Secrets Manager error: {e}")
        except Exception as e:
            logger.error(f"Error loading secrets: {e}")
        
        # Override with environment variables
        env_overrides = {
            'host': os.getenv('AURORA_HOST'),
            'port': os.getenv('AURORA_PORT'),
            'user': os.getenv('AURORA_USER'),
            'password': os.getenv('AURORA_PASSWORD'),
            'database': os.getenv('AURORA_DATABASE'),
        }
        
        for key, value in env_overrides.items():
            if value is not None:
                if key == 'port':
                    config[key] = int(value)
                else:
                    config[key] = value
        
        cls._validate_config(config)
        
        return config
    
    @classmethod
    def _validate_config(cls, config: Dict[str, Any]):
        """Validate database configuration"""
        required_fields = ['host', 'port', 'user', 'password', 'database']
        
        for field in required_fields:
            if not config.get(field):
                logger.error(f"Database {field} is not configured")
    
    @classmethod
    def get_connection_string(cls, use_secrets_manager: bool = True) -> str:
        """
        Get MySQL connection string
        """
        if use_secrets_manager:
            config = cls.load_from_secrets_manager()
        else:
            config = cls.DEFAULT_CONFIG
        
        # Build connection string
        conn_string = (
            f"mysql+mysqlconnector://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['database']}"
            f"?charset={config['charset']}"
            f"&ssl_ca={config['ssl_ca']}"
            f"&ssl_verify_cert={config['ssl_verify_cert']}"
        )
        
        return conn_string
    
    @classmethod
    def test_connection(cls) -> Dict[str, Any]:
        """
        Test database connection
        """
        import mysql.connector
        from mysql.connector import Error
        
        config = cls.load_from_secrets_manager()
        
        result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'error': None,
            'details': {}
        }
        
        try:
            connection = mysql.connector.connect(**config)
            cursor = connection.cursor()
            
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            
            cursor.execute("SELECT DATABASE()")
            database = cursor.fetchone()[0]
            
            cursor.execute("SHOW STATUS LIKE 'Uptime'")
            uptime = cursor.fetchone()[1]
            
            cursor.close()
            connection.close()
            
            result.update({
                'success': True,
                'details': {
                    'version': version,
                    'database': database,
                    'uptime_seconds': uptime,
                    'host': config['host'],
                    'port': config['port']
                }
            })
            
            logger.info(f"Database connection test successful")
            
        except Error as e:
            result['error'] = str(e)
            logger.error(f"Database connection test failed: {e}")
        
        return result

def get_db_config() -> Dict[str, Any]:
    """Convenience function to get database configuration"""
    return AuroraConfig.load_from_secrets_manager()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Aurora Configuration...")
    result = AuroraConfig.test_connection()
    
    if result['success']:
        print(f"Connection successful")
        print(f"Database: {result['details']['database']}")
        print(f"Version: {result['details']['version']}")
    else:
        print(f"Connection failed: {result['error']}")