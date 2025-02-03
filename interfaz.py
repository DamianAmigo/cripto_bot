import time
import logging
import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Usamos el estilo oscuro de matplotlib
plt.style.use("dark_background")

#############################
# CONFIGURACIÓN DE LOGGING  #
#############################

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

#########################################
# UTILIDADES: Conversión y Formateo     #
#########################################

def date_to_timestamp(date_str):
    """
    Convierte una fecha (YYYY-MM-DD) a timestamp en milisegundos.
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    timestamp = int(date_obj.timestamp() * 1000)
    return timestamp

def format_money(amount):
    """
    Formatea un monto numérico sin decimales y con el símbolo $.
    """
    return f"${amount:,.0f}"

#########################################
# OBTENCIÓN DE DATOS DE LA BASE DE DATOS
#########################################

def fetch_data_from_db(symbol, interval, start_date, end_date):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        start_timestamp = date_to_timestamp(start_date)
        end_timestamp = date_to_timestamp(end_date)
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candlestick_data
            WHERE symbol = %s AND interval = %s AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp;
        """
        cursor.execute(query, (symbol, interval, start_timestamp, end_timestamp))
        result = cursor.fetchall()
        data = pd.DataFrame(result, columns=["timestamp", "open", "high", "low", "close", "volume"])
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

#########################################
# ESTRATEGIAS DE TRADING                #
#########################################

def strategy_ema(data):
    """
    Estrategia basada en el cruce de la EMA de 10 y la de 50.
    Se genera 'buy' cuando EMA10 cruza hacia arriba EMA50 y 'sell' cuando cruza a la baja.
    Además, se calculan las EMAs para mostrarlas en el gráfico.
    """
    data = data.copy()
    data['EMA10'] = data['close'].ewm(span=10, adjust=False).mean()
    data['EMA50'] = data['close'].ewm(span=50, adjust=False).mean()
    
    signals = ['']  # sin señal para el primer dato
    for i in range(1, len(data)):
        if data['EMA10'].iloc[i] > data['EMA50'].iloc[i] and data['EMA10'].iloc[i-1] <= data['EMA50'].iloc[i-1]:
            signals.append('buy')
        elif data['EMA10'].iloc[i] < data['EMA50'].iloc[i] and data['EMA10'].iloc[i-1] >= data['EMA50'].iloc[i-1]:
            signals.append('sell')
        else:
            signals.append('')
    data['signals'] = signals
    return data

def strategy_trend_change(data):
    """
    Estrategia de cambio de tendencia simple: 
    Genera 'buy' si el precio cierra más alto que el cierre anterior y 'sell' en caso contrario.
    """
    data = data.copy()
    signals = ['']
    for i in range(1, len(data)):
        if data['close'].iloc[i] > data['close'].iloc[i-1]:
            signals.append('buy')
        elif data['close'].iloc[i] < data['close'].iloc[i-1]:
            signals.append('sell')
        else:
            signals.append('')
    data['signals'] = signals
    return data

#########################################
# SIMULACIÓN: CÁLCULO DEL RENDIMIENTO    #
#########################################

def calculate_profit(data, initial_capital, percent_per_trade):
    """
    Simula operaciones según las señales.
    Por simplicidad, en cada señal se invierte 'percent_per_trade' del capital.
    Esta función es una simulación muy básica.
    """
    capital = initial_capital
    trade_value = initial_capital * percent_per_trade / 100

    for i in range(1, len(data)):
        signal = data['signals'].iloc[i]
        price = data['close'].iloc[i]
        if signal == 'buy':
            # Simulamos compra y venta en la siguiente vela
            if i+1 < len(data):
                sell_price = data['close'].iloc[i+1]
                profit = (sell_price - price) * (trade_value / price)
                capital += profit
        elif signal == 'sell':
            if i+1 < len(data):
                buy_price = data['close'].iloc[i+1]
                loss = (price - buy_price) * (trade_value / price)
                capital -= loss
    return capital - initial_capital

def buy_and_hold(data, initial_capital):
    """
    Calcula el rendimiento de una estrategia Buy & Hold.
    """
    if len(data) == 0:
        return 0
    initial_price = data['close'].iloc[0]
    final_price = data['close'].iloc[-1]
    return (final_price - initial_price) * initial_capital / initial_price

#########################################
# GRAFICOS CON MATPLOTLIB EN TKINTER       #
#########################################

def plot_strategy(data, parent_frame, show_volume):
    """
    Dibuja el gráfico:
      - Si no se selecciona volumen, se muestra un gráfico de velas (línea de precio de cierre)
        y las EMAs (si existen) junto con las señales.
      - Si se selecciona mostrar volumen, se utiliza una cuadrícula con dos columnas:
        a la izquierda el gráfico de velas y a la derecha un gráfico de barras horizontales
        con el volumen (barras con 90% de transparencia y color celeste).
    """
    # Limpiar el frame padre
    for widget in parent_frame.winfo_children():
        widget.destroy()

    if show_volume:
        # Crear figura con GridSpec: 1 fila, 2 columnas (70% y 30%)
        fig = plt.figure(figsize=(8, 5))
        gs = GridSpec(1, 2, width_ratios=[7, 3])
        ax_price = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharey=ax_price)
    else:
        fig, ax_price = plt.subplots(figsize=(8, 5))
    
    # Configurar el gráfico de precio
    ax_price.plot(data['timestamp'], data['close'], label='Precio de Cierre', color='white', linewidth=1)
    
    # Si la estrategia utiliza EMA, mostrar las EMAs (si existen)
    if 'EMA10' in data.columns and 'EMA50' in data.columns:
        ax_price.plot(data['timestamp'], data['EMA10'], label='EMA 10', color='orange', linewidth=1.2)
        ax_price.plot(data['timestamp'], data['EMA50'], label='EMA 50', color='cyan', linewidth=1.2)
    
    # Marcar las señales (si existen)
    buy_points = data[data['signals'] == 'buy']
    sell_points = data[data['signals'] == 'sell']
    ax_price.scatter(buy_points['timestamp'], buy_points['close'], marker='^', color='lime', s=50, label='Compra')
    ax_price.scatter(sell_points['timestamp'], sell_points['close'], marker='v', color='red', s=50, label='Venta')
    
    ax_price.set_title("Gráfico de Velas e Indicadores", color="white")
    ax_price.set_xlabel("Fecha", color="white")
    ax_price.set_ylabel("Precio", color="white")
    ax_price.tick_params(axis='x', colors="white")
    ax_price.tick_params(axis='y', colors="white")
    ax_price.legend(facecolor="#333333", edgecolor="white", labelcolor="white")
    
    if show_volume:
        # Graficar volumen en barras horizontales en el eje derecho
        # Para ello, usamos el mismo eje de tiempo (convertido en números) para ajustar la orientación
        # Se crea una barra horizontal para cada vela.
        # Primero, se definen las posiciones (por ejemplo, usar índices)
        positions = range(len(data))
        # Usamos color celeste con 90% de transparencia (alpha = 0.1)
        ax_vol.barh(positions, data['volume'], color="#00CED1", alpha=0.1)
        ax_vol.set_xlabel("Volumen", color="white")
        ax_vol.set_yticks(positions)
        # Etiquetas de tiempo (se pueden ocultar para no saturar)
        ax_vol.set_yticklabels([])
        ax_vol.tick_params(axis='x', colors="white")
        ax_vol.tick_params(axis='y', colors="white")
        ax_vol.invert_yaxis()  # Para que el tiempo vaya en la misma dirección que en el gráfico de precio
        fig.tight_layout()
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

#########################################
# FUNCIÓN PARA EJECUTAR LA ESTRATEGIA     #
#########################################

def execute_strategy():
    # Leer los valores de la interfaz
    symbol = symbol_var.get()
    interval = interval_var.get()
    start_date = start_date_var.get()
    end_date = end_date_var.get()
    strategy_type = strategy_var.get()
    try:
        initial_capital = float(capital_var.get())
        percent_per_trade = float(percent_var.get())
    except ValueError:
        result_var.set("Error: El capital y el porcentaje deben ser numéricos.")
        return
    show_volume = volume_var.get()  # Booleano

    data = fetch_data_from_db(symbol, interval, start_date, end_date)
    if data is None or data.empty:
        result_var.set("Error: No se obtuvieron datos para el periodo especificado.")
        return

    # Aplicar la estrategia seleccionada
    if strategy_type == "EMA":
        data = strategy_ema(data)
    elif strategy_type == "Trend Change":
        data = strategy_trend_change(data)
    else:
        result_var.set("Error: Estrategia no válida.")
        return

    # Calcular rendimientos
    profit_strategy = calculate_profit(data, initial_capital, percent_per_trade)
    profit_buy_hold = buy_and_hold(data, initial_capital)

    # Actualizar los resultados formateados
    result_text = (f"Estrategia: {strategy_type}\n"
                   f"Capital Inicial: {format_money(initial_capital)}\n"
                   f"Rendimiento Estrategia: {format_money(profit_strategy)}\n"
                   f"Rendimiento Buy & Hold: {format_money(profit_buy_hold)}")
    result_var.set(result_text)
    
    # Dibujar el gráfico en el panel derecho
    plot_strategy(data, frame_right, show_volume)

#########################################
# CREACIÓN DE LA INTERFAZ GRÁFICA (MODO OSCURO)
#########################################

def create_interface():
    global symbol_var, interval_var, start_date_var, end_date_var, strategy_var, capital_var, percent_var, volume_var
    global frame_right, result_var

    root = tk.Tk()
    root.title("Análisis de Estrategias de Trading")
    root.geometry("1000x700")
    # Modo oscuro para la ventana principal
    root.configure(bg="#2e2e2e")

    # Dividir la ventana en tres secciones:
    # Panel izquierdo para parámetros (fijo), panel derecho para gráfico y panel inferior para resultados.
    frame_left = tk.Frame(root, width=300, bg="#2e2e2e", padx=10, pady=10)
    frame_left.pack(side=tk.LEFT, fill=tk.Y)
    global frame_right
    frame_right = tk.Frame(root, bg="#2e2e2e", padx=10, pady=10)
    frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    frame_bottom = tk.Frame(root, height=100, bg="#2e2e2e", padx=10, pady=10)
    frame_bottom.pack(side=tk.BOTTOM, fill=tk.X)

    # Panel izquierdo: Parámetros modificables
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
    strategy_var = tk.StringVar(value="EMA")
    ttk.Combobox(frame_left, textvariable=strategy_var, values=["EMA", "Trend Change"], state="readonly").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Capital Inicial (USD):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global capital_var
    capital_var = tk.StringVar(value="1000")
    tk.Entry(frame_left, textvariable=capital_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    tk.Label(frame_left, text="Porcentaje por Transacción (%):", fg="white", bg="#2e2e2e").pack(anchor="w")
    global percent_var
    percent_var = tk.StringVar(value="10")
    tk.Entry(frame_left, textvariable=percent_var, bg="#3e3e3e", fg="white").pack(fill=tk.X, pady=2)

    # Casilla para mostrar volumen
    global volume_var
    volume_var = tk.BooleanVar(value=False)
    tk.Checkbutton(frame_left, text="Mostrar Volumen", variable=volume_var, 
                   bg="#2e2e2e", fg="white", selectcolor="#2e2e2e").pack(anchor="w", pady=2)

    tk.Button(frame_left, text="Ejecutar Estrategia", command=execute_strategy, bg="#4e4e4e", fg="white").pack(pady=10)

    # Panel inferior: Resultados
    global result_var
    result_var = tk.StringVar()
    tk.Label(frame_bottom, textvariable=result_var, font=("Arial", 12), fg="white", bg="#2e2e2e", justify=tk.LEFT).pack(anchor="w")

    root.mainloop()

if __name__ == "__main__":
    create_interface()
