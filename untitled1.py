import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# Configuración de la página web
st.set_page_config(page_title="Escáner Cripto Pro Avanzado", page_icon="📈", layout="wide")

st.title("🚀 Escáner Cripto Pro con Confluencia Multi-Temporal y Gráficos")
st.write("Analiza el mercado de MEXC combinando temporalidades de 1h y 4h con indicadores técnicos avanzados.")

async def analizar_simbolo(exchange, symbol, semaphore):
    async with semaphore:
        try:
            # Descargar velas de 1h y 4h para análisis multi-temporal
            velas_1h = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            velas_4h = await exchange.fetch_ohlcv(symbol, timeframe='4h', limit=30)
            
            if len(velas_1h) < 30 or len(velas_4h) < 20:
                return None
                
            df_1h = pd.DataFrame(velas_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_4h = pd.DataFrame(velas_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            close_1h = df_1h['close']
            precio_actual = close_1h.iloc[-1]

            # --- 1. INDICADORES EN 1H ---
            delta = close_1h.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_actual = (100 - (100 / (1 + rs))).iloc[-1]

            exp1 = close_1h.ewm(span=12, adjust=False).mean()
            exp2 = close_1h.ewm(span=26, adjust=False).mean()
            macd_hist = ((exp1 - exp2) - (exp1 - exp2).ewm(span=9, adjust=False).mean()).iloc[-1]

            sma_20 = close_1h.rolling(20).mean()
            std_20 = close_1h.rolling(20).std()
            upper = (sma_20 + (2 * std_20)).iloc[-1]
            lower = (sma_20 - (2 * std_20)).iloc[-1]
            sma = sma_20.iloc[-1]

            vol_actual = df_1h['volume'].iloc[-1]
            vol_prom = df_1h['volume'].rolling(20).mean().iloc[-1]

            # --- 2. TENDENCIA MACRO EN 4H (Confluencia) ---
            close_4h = df_4h['close']
            sma_4h = close_4h.rolling(20).mean().iloc[-1]
            tendencia_4h_alcista = precio_actual > sma_4h

            # --- SISTEMA DE PUNTUACIÓN AVANZADO ---
            puntos_alcistas = 50

            # Confluencia 4h (Filtro de macro-tendencia)
            if tendencia_4h_alcista:
                puntos_alcistas += 10
            else:
                puntos_alcistas -= 10

            if macd_hist > 0: puntos_alcistas += 15
            else: puntos_alcistas -= 15

            if precio_actual <= lower * 1.01: puntos_alcistas += 20
            elif precio_actual >= upper * 0.99: puntos_alcistas -= 20
            elif precio_actual > sma: puntos_alcistas += 5

            if rsi_actual < 30: puntos_alcistas += 15
            elif rsi_actual > 70: puntos_alcistas -= 15

            if vol_actual > (vol_prom * 1.5):
                if macd_hist > 0: puntos_alcistas += 10
                else: puntos_alcistas -= 10

            prob_subir = max(0, min(100, int(puntos_alcistas)))
            prob_bajar = 100 - prob_subir

            return {
                'Cripto': symbol,
                'Precio ($)': round(precio_actual, 4),
                'Prob. Subir': f"{prob_subir}%",
                'Prob. Bajar': f"{prob_bajar}%",
                'RSI (1h)': round(rsi_actual, 1),
                'Tendencia': "🚀 ALCISTA" if prob_subir >= 75 else "🔻 BAJISTA",
                'raw_df': df_1h # Guardamos las velas para graficar después
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
if st.button("🔍 Iniciar Escaneo Multi-Temporal", type="primary"):
    with st.spinner("Analizando temporalidades de 1h y 4h en todo MEXC... Esto tomará unos segundos."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        destacados = loop.run_until_complete(ejecutar_escaneo())

        if destacados:
            st.success(f"¡Escaneo completado! Se encontraron {len(destacados)} oportunidades con alta confluencia.")
            
            # Guardar en la sesión de Streamlit para poder graficar sin volver a escanear
            st.session_state['destacados'] = destacados
        else:
            st.warning("No se encontraron criptomonedas cumpliendo los filtros estrictos en este momento.")

# Si ya hay resultados guardados en la sesión, mostramos la tabla y la sección de gráficos
if 'destacados' in st.session_state and st.session_state['destacados']:
    st.markdown("---")
    st.subheader("📋 Tabla de Resultados Destacados")
    
    # Preparamos dataframe sin la columna cruda para la tabla visual
    df_visible = pd.DataFrame([{k: v for k, v in r.items() if k != 'raw_df'} for r in st.session_state['destacados']])
    st.dataframe(df_visible, use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Gráfico Técnico Interactivo")
    st.write("Selecciona una criptomoneda de la lista para ver su comportamiento con Bandas de Bollinger:")

    simbolos_disponibles = [r['Cripto'] for r in st.session_state['destacados']]
    cripto_seleccionada = st.selectbox("Elige una criptomoneda:", simbolos_disponibles)

    # Buscar el dataframe de la cripto seleccionada
    crypto_data = next(r for r in st.session_state['destacados'] if r['Cripto'] == cripto_seleccionada)
    df_plot = crypto_data['raw_df']

    # Calcular Bandas de Bollinger para el gráfico
    df_plot['sma'] = df_plot['close'].rolling(20).mean()
    df_plot['std'] = df_plot['close'].rolling(20).std()
    df_plot['upper'] = df_plot['sma'] + (2 * df_plot['std'])
    df_plot['lower'] = df_plot['sma'] - (2 * df_plot['std'])
    df_plot['timestamp_dt'] = pd.to_datetime(df_plot['timestamp'], unit='ms')

    # Crear gráfico interactivo con Plotly (Velas + Bollinger)
    fig = go.Figure()

    # Velas japonesas
    fig.add_trace(go.Candlestick(
        x=df_plot['timestamp_dt'],
        open=df_plot['open'], high=df_plot['high'],
        low=df_plot['low'], close=df_plot['close'],
        name='Precio (1h)'
    ))

    # Bandas de Bollinger
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['upper'], line=dict(color='rgba(250, 0, 0, 0.5)', width=1), name='Banda Superior'))
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['sma'], line=dict(color='rgba(0, 0, 250, 0.5)', width=1), name='SMA 20'))
    fig.add_trace(go.Scatter(x=df_plot['timestamp_dt'], y=df_plot['lower'], line=dict(color='rgba(0, 250, 0, 0.5)', width=1), name='Banda Inferior', fill='tonexty', fillcolor='rgba(0, 250, 0, 0.05)'))

    fig.update_layout(
        title=f"Gráfico de Análisis Técnico: {cripto_seleccionada}",
        xaxis_title="Tiempo",
        yaxis_title="Precio (USDT)",
        template="plotly_dark",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)
