# app/config.py
import os

def _load_env_file(dotenv_path='.env'):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val

_load_env_file()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-secreta-capacitacion-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SUPERUSER_EMAIL = os.environ.get('SUPERUSER_EMAIL', 'admin@capacitacion.com')
    SUPERUSER_PASSWORD = os.environ.get('SUPERUSER_PASSWORD', 'admin1234')
    SUPERUSER_USERNAME = os.environ.get('SUPERUSER_USERNAME', 'SuperAdmin')

    # Suscripciones pagadas con AVAX en la testnet Fuji (Core wallet)
    AVAX_RPC_URL = os.environ.get('AVAX_RPC_URL', 'https://api.avax-test.network/ext/bc/C/rpc')
    AVAX_CHAIN_ID = int(os.environ.get('AVAX_CHAIN_ID', '43113'))
    AVAX_MERCHANT_ADDRESS = os.environ.get('AVAX_MERCHANT_ADDRESS', '')
    PRICE_INSTRUCTOR_AVAX = os.environ.get('PRICE_INSTRUCTOR_AVAX', '0.01')
    PRICE_ACADEMIA_AVAX = os.environ.get('PRICE_ACADEMIA_AVAX', '0.025')

