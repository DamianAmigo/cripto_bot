import pandas as pd

# Define el nombre de la estrategia (esto aparecerá en el menú desplegable)
strategy_name = "EMA"

def apply_strategy(data):
    """
    Aplica la estrategia de cruce de EMAs (10 y 50 periodos) al DataFrame 'data'.
    Se calculan las EMAs y se generan señales 'buy' y 'sell'.
    Devuelve el DataFrame modificado.
    """
    data = data.copy()
    data['EMA10'] = data['close'].ewm(span=10, adjust=False).mean()
    data['EMA50'] = data['close'].ewm(span=50, adjust=False).mean()
    
    signals = ['']  # Sin señal para la primera vela
    for i in range(1, len(data)):
        if data['EMA10'].iloc[i] > data['EMA50'].iloc[i] and data['EMA10'].iloc[i-1] <= data['EMA50'].iloc[i-1]:
            signals.append('buy')
        elif data['EMA10'].iloc[i] < data['EMA50'].iloc[i] and data['EMA10'].iloc[i-1] >= data['EMA50'].iloc[i-1]:
            signals.append('sell')
        else:
            signals.append('')
    data['signals'] = signals
    return data
