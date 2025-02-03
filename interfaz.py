import os
import importlib.util
import logging
import pandas as pd
from datetime import datetime
import psycopg2
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import mplfinance as mpf  # Para gráficos de velas japonesas

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#############################
# CONEXIÓN A LA BASE DE DATOS
#############################

def get_db_connection():
    try:
        conn = psycopg2.connect(dbname="cripto_db", user="cripto_user", password="demitrico1", host="localhost")
        return conn
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise

#############################
# UTILIDADES: Conversión y Formateo
#############################

def date_to_timestamp(date_str):
    """Convierte una fecha (YYYY-MM-DD) a timestamp en milisegundos."""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    timestamp = int(date_obj.timestamp() * 1000)
    return timestamp

def format_money(amount):
    """Formatea un monto sin decimales y con el símbolo $."""
    return f"${amount:,.0f}"

#############################
# OBTENCIÓN DE DATOS DE LA BASE DE DATOS
#############################

def fetch_data_from_db(symbol, interval, start_date, end_date):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        start_ts = date_to_timestamp(start_date)
        end_ts = date_to_timestamp(end_date)
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candlestick_data
            WHERE symbol = %s AND interval = %s AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp;
        """
        cursor.execute(query, (symbol, interval, start_ts, end_ts))
        result = cursor.fetchall()
        data = pd.DataFrame(result, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # Convertir a datetime
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
        return data
    except Exception as e:
        logging.error(f"Error al obtener datos de la base de datos: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#############################
# FUNCIONES PARA GRAFICAR
#############################

def plot_candlestick(data, parent_frame, show_volume):
    """
    Crea un gráfico de velas japonesas con mplfinance.
    Si show_volume es True, se muestra el gráfico de volumen.
    Se sobreponen los indicadores (si existen columnas EMA10 y EMA50).
    """
    # Convertir el DataFrame al formato que usa mplfinance:
    data = data.set_index("timestamp")
    
    # Definir el estilo oscuro para mplfinance
    mc = mpf.make_marketcolors(up='lime', down='red', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc)
    
    add_plots = []
    if "EMA10" in data.columns and "EMA50" in data.columns:
        add_plots = [
            mpf.make_addplot(data["EMA10"], color="orange"),
            mpf.make_addplot(data["EMA50"], color="cyan")
        ]
    
    # Crear la figura de mplfinance
    fig, axlist = mpf.plot(data,
                           type='candle',
                           volume=show_volume,
                           addplot=add_plots,
                           style=s,
                           returnfig=True)
    
    # Integrar la figura en Tkinter
    for widget in parent_frame.winfo_children():
        widget.destroy()
    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

#############################
# DINÁMICA DE ESTRATEGIAS
#############################

def load_strategies():
    """
    Escanea la carpeta 'estrategias' y carga los módulos de estrategia.
    Se espera que cada módulo tenga:
      - Una variable 'strategy_name' (string)
      - Una función 'apply_strategy(data)' que devuelve el DataFrame modificado.
    Retorna un diccionario {strategy_name: module}.
    """
    strategies = {}
    folder = "estrategias"
    if not os.path.isdir(folder):
        logging.error(f"No se encontró la carpeta '{folder}'.")
        return strategies
    for file in os.listdir(folder):
        if file.endswith(".py") and file != "__init__.py":
            module_name = file[:-3]
            path = os.path.join(folder, file)
            spec = importlib.util.spec_from_file_location(module_name, path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, "strategy_name") and hasattr(mod, "apply_strategy"):
                    strategies[mod.strategy_name] = mod
                    logging.info(f"Estrategia cargada: {mod.strategy_name}")
                else:
                    logging.warning(f"El módulo {module_name} no define 'strategy_name' o 'apply_strategy'.")
            except Exception as e:
                logging.error(f"Error al cargar {module_name}: {e}")
    return strategies

#############################
# SIMULACIÓN: CALCULO DEL RENDIMIENTO
#############################

def calculate_profit(data, initial_capital, percent_per_trade):
    """
    Simula operaciones muy básicas basadas en las señales.
    Cada operación invierte 'percent_per_trade' % del capital.
    """
    capital = initial_capital
    trade_value = initial_capital * percent_per_trade / 100
    for i in range(1, len(data)):
        signal = data['signals'].iloc[i]
        price = data['close'].iloc[i]
        if signal == 'buy' and i+1 < len(data):
            sell_price = data['close'].iloc[i+1]
            profit = (sell_price - price) * (trade_value / price)
            capital += profit
        elif signal == 'sell' and i+1 < len(data):
            buy_price = data['close'].iloc[i+1]
            loss = (price - buy_price) * (trade_value / price)
            capital -= loss
    return capital - initial_capital

def buy_and_hold(data, initial_capital):
    """Calcula el rendimiento Buy & Hold."""
    if len(data) == 0:
        return 0
    initial_price = data['close'].iloc[0]
    final_price = data['close'].iloc[-1]
    return (final_price - initial_price) * initial_capital / initial_price

#############################
# INTERFAZ GRÁFICA (MODO OSCURO)
#############################

def execute_strategy():
    # Leer parámetros de la interfaz
    symbol = symbol_var.get()
    interval = interval_var.get()
    start_date = start_date_var.get()
    end_date = end_date_var.get()
    selected_strategy = strategy_var.get()
    try:
        initial_capital = float(capital_var.get())
        percent_per_trade = float(percent_var.get())
    except ValueError:
        result_var.set("Error: Capital y porcentaje deben ser numéricos.")
        return
    show_volume = volume_var.get()
    
    data = fetch_data_from_db(symbol, interval, start_date, end_date)
    if data is None or data.empty:
        result_var.set("Error: No se obtuvieron datos para el periodo especificado.")
        return

    # Cargar la estrategia seleccionada desde la carpeta 'estrategias'
    if selected_strategy in strategies_dict:
        strategy_mod = strategies_dict[selected_strategy]
        try:
            data = strategy_mod.apply_strategy(data)
        except Exception as e:
            result_var.set(f"Error al aplicar la estrategia: {e}")
            return
    else:
        result_var.set("Error: Estrategia no encontrada.")
        return

    # Calcular rendimientos
    profit_strategy = calculate_profit(data, initial_capital, percent_per_trade)
    profit_buy_hold = buy_and_hold(data, initial_capital)
    
    # Actualizar resultados (formateados)
    result_text = (f"Estrategia: {selected_strategy}\n"
                   f"Capital Inicial: {format_money(initial_capital)}\n"
                   f"Rendimiento Estrategia: {format_money(profit_strategy)}\n"
                   f"Rendimiento Buy & Hold: {format_money(profit_buy_hold)}")
    result_var.set(result_text)
    
    # Graficar velas japonesas con indicadores y volumen (si corresponde)
    plot_candlestick(data, frame_right, show_volume)

def create_interface():
    global symbol_var, interval_var, start_date_var, end_date_var, strategy_var, capital_var, percent_var, volume_var, result_var, frame_right, strategies_dict

    root = tk.Tk()
    root.title("Análisis de Estrategias de Trading")
    root.geometry("1200x700")
    root.configure(bg="#2e2e2e")

    # Panel izquierdo: Parámetros
    frame_left = tk.Frame(root, width=300, bg="#2e2e2e", padx=10, pady=10)
    frame_left.pack(side=tk.LEFT, fill=tk.Y)

    # Panel derecho: Gráfico
    frame_right = tk.Frame(root, bg="#2e2e2e", padx=10, pady=10)
    frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Panel inferior: Resultados
    frame_bottom = tk.Frame(root, height=100, bg="#2e2e2e", padx=10, pady=10)
    frame_bottom.pack(side=tk.BOTTOM, fill=tk.X)

    tk.Label(frame_left, text="Parámetros de Entrada", font=("Arial", 14, "bold"), fg="white", bg="#2e2e2e").pack(pady=5)
    tk.Label(frame_left, text="Símbolo:", fg="white", bg="#2e2e2e").pack(anchor="w")
    global symbol_var
    symbol_var = tk.StringVar(value="BTCUSDT")
    tk.Entry(frame_left, textvariable=symbol_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Intervalo:", fg="white", bg="#2e2e2e").pack(anchor="w")
    global interval_var
    interval_var = tk.StringVar(value="1h")
    ttk.Combobox(frame_left, textvariable=interval_var, values=["1m","5m","15m","30m","1h","1d"], state="readonly").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Fecha de Inicio (YYYY-MM-DD):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global start_date_var
    start_date_var = tk.StringVar(value="2017-01-01")
    tk.Entry(frame_left, textvariable=start_date_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Fecha de Fin (YYYY-MM-DD):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global end_date_var
    end_date_var = tk.StringVar(value="2017-02-03")
    tk.Entry(frame_left, textvariable=end_date_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Estrategia:", fg="white", bg="#2e2e2e").pack(anchor="w")
    global strategy_var
    # Cargar estrategias dinámicamente desde la carpeta "estrategias"
    strategies_dict = load_strategies()
    strategy_names = list(strategies_dict.keys())
    if not strategy_names:
        strategy_names = ["Sin estrategias"]
    strategy_var = tk.StringVar(value=strategy_names[0])
    ttk.Combobox(frame_left, textvariable=strategy_var, values=strategy_names, state="readonly").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Capital Inicial (USD):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global capital_var
    capital_var = tk.StringVar(value="1000")
    tk.Entry(frame_left, textvariable=capital_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Porcentaje por Transacción (%):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global percent_var
    percent_var = tk.StringVar(value="10")
    tk.Entry(frame_left, textvariable=percent_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    global volume_var
    volume_var = tk.BooleanVar(value=False)
    tk.Checkbutton(frame_left, text="Mostrar Volumen", variable=volume_var, bg="#2e2e2e", fg="white", selectcolor="#2e2e2e").pack(anchor="w", pady=2)

    tk.Button(frame_left, text="Ejecutar Estrategia", command=execute_strategy, bg="#4e4e4e", fg="white").pack(pady=10)

    global result_var
    result_var = tk.StringVar()
    tk.Label(frame_bottom, textvariable=result_var, font=("Arial", 12), fg="white", bg="#2e2e2e", justify=tk.LEFT).pack(anchor="w")

    root.mainloop()

if __name__ == "__main__":
    # Cargar estrategias de la carpeta "estrategias"
    strategies_dict = load_strategies()
    create_interface()
