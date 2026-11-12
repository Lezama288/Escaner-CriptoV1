import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# Configuración de la página web
st.set_page_config(page_title="Escáner Cripto Pro MACD 4T", page_icon="📈", layout="wide")

st.title("🚀 Escáner Cripto Pro con Confluencia Total de MACD y 4 Temporalidades")
st.write("Analiza y evalúa el impulso del **MACD en 1m, 15m, 1h y 4h** junto con Bandas de Bollinger y RSI.")

def calcular_macd_hist(df):
    """Calcula el último valor del histograma MACD (12, 26, 9)"""
    close = df['close']
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    return hist.iloc[-1]

async def analizar_simbolo(exchange, symbol, semaphore):
    async with semaphore:
        try:
            # Descargar velas para las 4 temporalidades con suficiente profundidad (50 velas)
            v_1m, v_15m, v_1h, v_4h = await asyncio.gather(
                exchange.fetch_ohlcv(symbol, timeframe='1m', limit=50),
                exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50),
                exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50),
                exchange.fetch_ohlcv(symbol, timeframe='4h', limit=50)
            )
            
            if len(v_1m) < 35 or len(v_15m) < 35 or len(v_1h) < 35 or len(v_4h) < 35:
                return None
                
            df_1m = pd.DataFrame(v_1m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_15m = pd.DataFrame(v_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_1h = pd.DataFrame(v_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_4h = pd.DataFrame(v_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            precio_actual = df_1h['close'].iloc[-1]

            # --- 1. INDICADORES EN 1H (Base principal) ---
            close_1h = df_1h['close']
            delta = close_1h.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_actual = (100 - (100 / (1 + rs))).iloc[-1]

            sma_20 = close_1h.rolling(20).mean()
            std_20 = close_1h.rolling(20).std()
            upper = (sma_20 + (2 * std_20)).iloc[-1]
            lower = (sma_20 - (2 * std_20)).iloc[-1]
            sma = sma_20.iloc[-1]

            vol_actual = df_1h['volume'].iloc[-1]
            vol_prom = df_1h['volume'].rolling(20).mean().iloc[-1]

            # --- 2. MACD EN LAS 4 TEMPORALIDADES ---
            macd_1m = calcular_macd_hist(df_1m)
            macd_15m = calcular_macd_hist(df_15m)
            macd_1h = calcular_macd_hist(df_1h)
            macd_4h = calcular_macd_hist(df_4h)

            # --- 3. TENDENCIA DE MEDIAS MÓVILES EN 4 Tiempos ---
            alcista_1m = precio_actual > df_1m['close'].rolling(20).mean().iloc[-1]
            alcista_15m = precio_actual > df_15m['close'].rolling(20).mean().iloc[-1]
            alcista_1h = precio_actual > sma
            alcista_4h = precio_actual > df_4h['close'].rolling(20).mean().iloc[-1]

            # --- SISTEMA DE PUNTUACIÓN MULTI-TEMPORAL Y MACD ---
            puntos_alcistas = 50

            # Puntuación por tendencia de precios en 4T
            if alcista_4h: puntos_alcistas += 6
            else: puntos_alcistas -= 6
            if alcista_1h: puntos_alcistas += 5
            else: puntos_alcistas -= 5
            if alcista_15m: puntos_alcistas += 4
            else: puntos_alcistas -= 4
            if alcista_1m: puntos_alcistas += 3
            else: puntos_alcistas -= 3

            # Puntuación por confluencia de MACD en los 4 tiempos
            if macd_4h > 0: puntos_alcistas += 10
            else: puntos_alcistas -= 10
            if macd_1h > 0: puntos_alcistas += 8
            else: puntos_alcistas -= 8
            if macd_15m > 0: puntos_alcistas += 6
            else: puntos_alcistas -= 6
            if macd_1m > 0: puntos_alcistas += 4
            else: puntos_alcistas -= 4

            # Bollinger y RSI
            if precio_actual <= lower * 1.01: puntos_alcistas += 10
            elif precio_actual >= upper * 0.99: puntos_alcistas -= 10

            if rsi_actual < 30: puntos_alcistas += 8
            elif rsi_actual > 70: puntos_alcistas -= 8

            if vol_actual > (vol_prom * 1.5):
                if macd_1h > 0: puntos_alcistas += 5
                else: puntos_alcistas -= 5

            prob_subir = max(0, min(100, int(puntos_alcistas)))
            prob_bajar = 100 - prob_subir

            conteo_tendencia = sum([alcista_1m, alcista_15m, alcista_1h, alcista_4h])

            return {
                'Cripto': symbol,
                'Precio ($)': round(precio_actual, 4),
                'Prob. Subir': f"{prob_subir}%",
                'Prob. Bajar': f"{prob_bajar}%",
                'Alineación (4T)': f"{conteo_tendencia}/4",
                'MACD 1m': "🟢" if macd_1m > 0 else "🔴",
                'MACD 15m': "🟢" if macd_15m > 0 else "🔴",
                'MACD 1h': "🟢" if macd_1h > 0 else "🔴",
                'MACD 4h': "🟢" if macd_4h > 0 else "🔴",
                'RSI (1h)': round(rsi_actual, 1),
                'Tendencia': "🚀 ALCISTA" if prob_subir >= 75 else "🔻 BAJISTA",
                'raw_df': df_1h
            }
        except Exception:
            return None

async def ejecutar_escaneo():
    exchange = ccxt.mexc({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    markets = await exchange.load_markets()
    simbolos = [s for s, m in markets.items() if s.endswith('/USDT') and m['active']]

    semaphore = asyncio.Semaphore(10)
    tareas = [analizar_simbolo(exchange, s, semaphore) for s in simbolos]
    resultados = await asyncio.gather(*tareas)
    await exchange.close()

    resultados_validos = [r for r in resultados if r is not None]
    resultados_validos.sort(key=lambda x: int(x['Prob. Subir'].replace('%', '')), reverse=True)
    
    return [r for r in resultados_validos if int(r['Prob. Subir'].replace('%', '')) >= 75 or int(r['Prob. Bajar'].replace('%', '')) >= 75]

# Botón interactivo principal
if st.button("🔍 Iniciar Escaneo Pro (4T + MACD en 4 Marcos)", type="primary"):
    with st.spinner("Analizando confluencia completa de 1m, 15m, 1h y 4h (Precios + MACD)... Un momento."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        destacados = loop.run_until_complete(ejecutar_escaneo())

        if destacados:
            st.success(f"¡Escaneo completado! Se encontraron {len(destacados)} oportunidades con alta confluencia.")
            st.session_state['destacados'] = destacados
        else:
            st.warning("No se encontraron criptomonedas cumpliendo los filtros estrictos en este momento.")

# Mostrar tabla y gráficos interactivos si hay resultados
if 'destacados' in st.session_state and st.session_state['destacados']:
    st.markdown("---")
    st.subheader("📋 Tabla de Resultados Avanzada")
    
    df_visible = pd.DataFrame([{k: v for k, v in r.items() if k != 'raw_df'} for r in st.session_state['destacados']])
    st.dataframe(df_visible, use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Gráfico Técnico Interactivo (1h)")
    simbolos_disponibles = [r['Cripto'] for r in st.session_state['destacados']]
    cripto_seleccionada = st.selectbox("Elige una criptomoneda para visualizar:", simbolos_disponibles)

    crypto_data = next(r for r in st.session_state['destacados'] if r['Cripto'] == cripto_seleccionada)
    df_plot = crypto_data['raw_df']

    df_plot['sma'] = df_plot['close'].rolling(20).mean()
    df_plot['std'] = df_plot['close'].rolling(20).std()
    df_plot['upper'] = df_plot['sma'] + (2 * df_plot['std'])
    df_plot['lower'] = df_plot['sma'] - (2 * df_plot['std'])
    df_plot['timestamp_dt'] = pd.to_datetime(df_plot['timestamp'], unit='ms')

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_plot['timestamp_dt'],
        open=df_plot['open'], high=df_plot['high'],
        low=df_plot['low'], close=df_plot['close'],
        name='Precio (1h)'
    ))
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['upper'], line=dict(color='rgba(250, 0, 0, 0.5)', width=1), name='Banda Superior'))
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['sma'], line=dict(color='rgba(0, 0, 250, 0.5)', width=1), name='SMA 20'))
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['lower'], line=dict(color='rgba(0, 250, 0, 0.5)', width=1), name='Banda Inferior', fill='tonexty', fillcolor='rgba(0, 250, 0, 0.05)'))

    fig.update_layout(
        title=f"Análisis Técnico de {cripto_seleccionada}",
        xaxis_title="Tiempo",
        yaxis_title="Precio (USDT)",
        template="plotly_dark",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)
