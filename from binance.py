import time
import logging
from binance.client import Client
from datetime import datetime
import psycopg2
from psycopg2 import sql
from psycopg2.errors import UniqueViolation

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuración de la API de Binance
api_key = 'tu_api_key'  # Reemplaza con tu API Key
api_secret = 'tu_api_secret'  # Reemplaza con tu API Secret
client = Client(api_key, api_secret)

# Conexión a la base de datos PostgreSQL
def get_db_connection():
    try:
        conn = psycopg2.connect(dbname="cripto_db", user="cripto_user", password="demitrico1", host="localhost")
        return conn
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise

# Función para obtener el último timestamp registrado en la base de datos
def get_last_timestamp(symbol, interval):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consulta el último timestamp registrado en la base de datos para ese símbolo e intervalo
        cursor.execute("""
            SELECT MAX(timestamp) FROM candlestick_data
            WHERE symbol = %s AND interval = %s;
        """, (symbol, interval))

        result = cursor.fetchone()
        last_timestamp = result[0] if result[0] else None
        logging.info(f"Último timestamp registrado para {symbol} con intervalo {interval}: {last_timestamp}")

        return last_timestamp
    except Exception as e:
        logging.error(f"Error al obtener el último timestamp: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Función para obtener los datos de Binance a partir de un timestamp específico
def fetch_binance_data(symbol, interval, start_date, last_timestamp=None):
    try:
        if last_timestamp:
            # Convertir el último timestamp en formato ISO (fecha y hora) para la consulta
            start_date = datetime.utcfromtimestamp(last_timestamp / 1000).strftime('%d %b, %Y %H:%M:%S')

        # Descargar los datos históricos de Binance
        klines = client.get_historical_klines(symbol, interval, start_date)
        print("intentando obtener datos")
        logging.info(f"Datos obtenidos para {symbol} desde {start_date} con intervalo {interval}. Total de {len(klines)} registros.")
        return klines
    except Exception as e:
        logging.error(f"Error al obtener datos de Binance: {e}")
        raise

# Función para guardar los datos en la base de datos
def save_to_db(data, symbol, interval):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for entry in data:
            timestamp = int(entry[0])
            open_price = float(entry[1])
            high_price = float(entry[2])
            low_price = float(entry[3])
            close_price = float(entry[4])
            volume = float(entry[5])
            quote_asset_volume = float(entry[7])
            number_of_trades = int(entry[8])
            taker_buy_base_asset_volume = float(entry[9])
            taker_buy_quote_asset_volume = float(entry[10])

            # Inserción de datos en la tabla candlestick_data
            print("incertando datos en la tabla candlestick_data")
            cursor.execute("""
                INSERT INTO candlestick_data (
                    timestamp, symbol, interval, open, high, low, close, volume, 
                    quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, 
                    taker_buy_quote_asset_volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, symbol, interval) DO NOTHING;
            """, (timestamp, symbol, interval, open_price, high_price, low_price, close_price, 
                  volume, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, 
                  taker_buy_quote_asset_volume))
        
        conn.commit()
        logging.info(f"Datos de {symbol} con intervalo {interval} insertados correctamente.")
    except UniqueViolation:
        logging.warning(f"Datos duplicados para {symbol} en el intervalo {interval}. Se omiten.")
    except Exception as e:
        logging.error(f"Error al guardar datos en la base de datos: {e}")
        conn.rollback()  # Deshacer la transacción en caso de error
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Función principal para descargar y almacenar datos
def main(symbol, interval, start_date, end_date=None):
    try:
        # Paso 1: Obtener el último timestamp registrado en la base de datos
        last_timestamp = get_last_timestamp(symbol, interval)

        # Paso 2: Si ya hay datos, obtener los nuevos datos a partir del último timestamp
        data = fetch_binance_data(symbol, interval, start_date, last_timestamp)

        # Paso 3: Guardar los nuevos datos en la base de datos
        save_to_db(data, symbol, interval)
    except Exception as e:
        logging.error(f"Error en la ejecución del script: {e}")

if __name__ == '__main__':
    symbol = 'BTCUSDT'  # Par de trading
    interval = '1h'  # Intervalo, por ejemplo, 1m, 5m, 1h, 1d
    start_date = '1 Jan, 2017'  # Fecha de inicio

    # Ejecutar el script
    main(symbol, interval, start_date)
    
    # Para ejecución periódica puedes usar un ciclo con un retraso
    # por ejemplo, ejecutar cada hora
    while True:
        try:
            logging.info("Ejecutando descarga de datos...")
            main(symbol, interval, start_date)  # Vuelve a descargar los datos
            time.sleep(3600)  # Esperar una hora antes de ejecutar nuevamente
        except Exception as e:
            logging.error(f"Error en la ejecución programada: {e}")
            time.sleep(60)  # Espera de 1 minuto antes de intentar nuevamente
