import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import streamlit as st

# Configuración de la página web
st.set_page_config(page_title="Escáner Cripto Pro", page_icon="📈", layout="wide")

st.title("🚀 Escáner de Mercado Cripto en Tiempo Real")
st.write("Haz clic en el botón de abajo para escanear el mercado de MEXC utilizando indicadores técnicos avanzados (RSI, MACD y Bandas de Bollinger).")

async def analizar_simbolo(exchange, symbol, semaphore):
    async with semaphore:
        try:
            velas = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            if len(velas) < 30:
                return None
                
            df = pd.DataFrame(velas, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            close = df['close']
            precio_actual = close.iloc[-1]

            # 1. RSI (14)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_actual = (100 - (100 / (1 + rs))).iloc[-1]

            # 2. MACD (12, 26, 9)
            exp1 = close.ewm(span=12, adjust=False).mean()
            exp2 = close.ewm(span=26, adjust=False).mean()
            macd_hist = ((exp1 - exp2) - (exp1 - exp2).ewm(span=9, adjust=False).mean()).iloc[-1]

            # 3. Bandas de Bollinger (20, 2)
            sma_20 = close.rolling(20).mean()
            std_20 = close.rolling(20).std()
            upper = (sma_20 + (2 * std_20)).iloc[-1]
            lower = (sma_20 - (2 * std_20)).iloc[-1]
            sma = sma_20.iloc[-1]

            # 4. Volumen
            vol_actual = df['volume'].iloc[-1]
            vol_prom = df['volume'].rolling(20).mean().iloc[-1]

            # Sistema de Puntuación
            puntos_alcistas = 50
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
                'RSI': round(rsi_actual, 1),
                'Tendencia': "🚀 ALCISTA" if prob_subir >= 75 else "🔻 BAJISTA"
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

# Botón interactivo en la página web
if st.button("🔍 Iniciar Escaneo de Mercado", type="primary"):
    with st.spinner("Analizando cientos de criptomonedas en tiempo real... Por favor espera unos segundos."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        destacados = loop.run_until_complete(ejecutar_escaneo())

        if destacados:
            st.success(f"¡Escaneo completado! Se encontraron {len(destacados)} criptos con alta probabilidad.")
            df_final = pd.DataFrame(destacados)
            st.dataframe(df_final, use_container_width=True)
        else:
            st.warning("No se encontraron criptomonedas cumpliendo los filtros estrictos en este momento.")
