import asyncio
import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Configuración de la página web
st.set_page_config(
    page_title="Terminal Cripto Pro - Volumen Real",
    page_icon="📈",
    layout="wide",
)

# Estilo visual personalizado (Terminal institucional)
st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1a1c24; padding: 15px; border-radius: 10px; border: 1px solid #30333d; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title(
    "🚀 Terminal de Escaneo Cripto Pro (Filtro de Liquidez + Perfil de"
    " Volumen)"
)
st.markdown(
    "Análisis multi-temporal (**1m, 15m, 1h, 4h**) enfocado en los activos de"
    " **mayor volumen y liquidez** de MEXC."
)

# --- BARRA LATERAL (CONFIGURACIÓN & WATCHLIST) ---
st.sidebar.header("⚙️ Configuración del Escáner")
modo_escaneo = st.sidebar.radio(
    "Selecciona el Modo:",
    [
        "Top Activos por Volumen (Alta Liquidez)",
        "Mi Watchlist Personalizada",
    ],
)

watchlist_default = (
    "BTC/USDT\nETH/USDT\nSOL/USDT\nXRP/USDT\nADA/USDT\nDOGE/USDT\nAVAX/USDT\nLINK/USDT\nPEPE/USDT\nRENDER/USDT"
)
simbolos_personalizados = None

if modo_escaneo == "Mi Watchlist Personalizada":
  user_watchlist = st.sidebar.text_area(
      "Introduce tus criptos (formato PAR/USDT, una por línea):",
      watchlist_default,
      height=150,
  )
  simbolos_personalizados = [
      s.strip().upper() for s in user_watchlist.split("\n") if s.strip()
  ]


def calcular_macd_hist(df):
  close = df["close"]
  exp1 = close.ewm(span=12, adjust=False).mean()
  exp2 = close.ewm(span=26, adjust=False).mean()
  macd_line = exp1 - exp2
  signal_line = macd_line.ewm(span=9, adjust=False).mean()
  hist = macd_line - signal_line
  return hist.iloc[-1]


def calcular_perfil_volumen(df):
  """Calcula el Punto de Control (POC) aproximado basado en volumen y precio"""
  try:
    precio_min = df["low"].min()
    precio_max = df["high"].max()
    if precio_min == precio_max:
      return df["close"].iloc[-1]
    bins = np.linspace(precio_min, precio_max, 15)
    df["bin"] = pd.cut(df["close"], bins=bins, include_lowest=True)
    vol_por_bin = df.groupby("bin", observed=False)["volume"].sum()
    if vol_por_bin.empty:
      return df["close"].iloc[-1]
    poc_bin = vol_por_bin.idxmax()
    poc_precio = (poc_bin.left + poc_bin.right) / 2
    return round(poc_precio, 4)
  except:
    return df["close"].iloc[-1]


async def analizar_simbolo(exchange, symbol, semaphore):
  async with semaphore:
    try:
      v_1m, v_15m, v_1h, v_4h = await asyncio.gather(
          exchange.fetch_ohlcv(symbol, timeframe="1m", limit=50),
          exchange.fetch_ohlcv(symbol, timeframe="15m", limit=50),
          exchange.fetch_ohlcv(symbol, timeframe="1h", limit=50),
          exchange.fetch_ohlcv(symbol, timeframe="4h", limit=50),
      )

      if (
          len(v_1m) < 35
          or len(v_15m) < 35
          or len(v_1h) < 35
          or len(v_4h) < 35
      ):
        return None

      df_1m = pd.DataFrame(
          v_1m, columns=["timestamp", "open", "high", "low", "close", "volume"]
      )
      df_15m = pd.DataFrame(
          v_15m, columns=["timestamp", "open", "high", "low", "close", "volume"]
      )
      df_1h = pd.DataFrame(
          v_1h, columns=["timestamp", "open", "high", "low", "close", "volume"]
      )
      df_4h = pd.DataFrame(
          v_4h, columns=["timestamp", "open", "high", "low", "close", "volume"]
      )

      precio_actual = df_1h["close"].iloc[-1]

      # Indicadores 1h
      close_1h = df_1h["close"]
      delta = close_1h.diff()
      gain = delta.where(delta > 0, 0).rolling(14).mean()
      loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
      rs = gain / loss
      rsi_actual = (100 - (100 / (1 + rs))).iloc[-1]

      sma_20 = close_1h.rolling(20).mean()
      std_20 = close_1h.rolling(20).std()
      upper = (sma_20 + (2 * std_20)).iloc[-1]
      lower = (sma_20 - (2 * std_20)).iloc[-1]
      sma = sma_20.iloc[-1]

      vol_actual = df_1h["volume"].iloc[-1]
      vol_prom = df_1h["volume"].rolling(20).mean().iloc[-1]

      # MACD en 4 Tiempos
      macd_1m = calcular_macd_hist(df_1m)
      macd_15m = calcular_macd_hist(df_15m)
      macd_1h = calcular_macd_hist(df_1h)
      macd_4h = calcular_macd_hist(df_4h)

      # Tendencia de Precios en 4 Tiempos
      alcista_1m = precio_actual > df_1m["close"].rolling(20).mean().iloc[-1]
      alcista_15m = precio_actual > df_15m["close"].rolling(20).mean().iloc[-1]
      alcista_1h = precio_actual > sma
      alcista_4h = precio_actual > df_4h["close"].rolling(20).mean().iloc[-1]

      # Puntuación
      puntos_alcistas = 50
      if alcista_4h:
        puntos_alcistas += 6
      else:
        puntos_alcistas -= 6
      if alcista_1h:
        puntos_alcistas += 5
      else:
        puntos_alcistas -= 5
      if alcista_15m:
        puntos_alcistas += 4
      else:
        puntos_alcistas -= 4
      if alcista_1m:
        puntos_alcistas += 3
      else:
        puntos_alcistas -= 3

      if macd_4h > 0:
        puntos_alcistas += 10
      else:
        puntos_alcistas -= 10
      if macd_1h > 0:
        puntos_alcistas += 8
      else:
        puntos_alcistas -= 8
      if macd_15m > 0:
        puntos_alcistas += 6
      else:
        puntos_alcistas -= 6
      if macd_1m > 0:
        puntos_alcistas += 4
      else:
        puntos_alcistas -= 4

      if precio_actual <= lower * 1.01:
        puntos_alcistas += 10
      elif precio_actual >= upper * 0.99:
        puntos_alcistas -= 10

      if rsi_actual < 30:
        puntos_alcistas += 8
      elif rsi_actual > 70:
        puntos_alcistas -= 8

      if vol_actual > (vol_prom * 1.5):
        if macd_1h > 0:
          puntos_alcistas += 5
        else:
          puntos_alcistas -= 5

      prob_subir = max(0, min(100, int(puntos_alcistas)))
      prob_bajar = 100 - prob_subir
      conteo_tendencia = sum([alcista_1m, alcista_15m, alcista_1h, alcista_4h])

      # --- GESTIÓN DE RIESGO ---
      poc = calcular_perfil_volumen(df_1h)
      stop_loss = round(min(lower * 0.99, poc * 0.98, precio_actual * 0.97), 4)
      riesgo = precio_actual - stop_loss
      take_profit = round(precio_actual + (riesgo * 2.0), 4)

      return {
          "Cripto": symbol,
          "Precio ($)": round(precio_actual, 4),
          "POC (Vol)": poc,
          "Prob_Subir_Num": prob_subir,
          "Prob. Subir": f"{prob_subir}%",
          "Stop Loss ($)": stop_loss,
          "Take Profit ($)": take_profit,
          "Alineación (4T)": f"{conteo_tendencia}/4",
          "MACD 1m": "🟢" if macd_1m > 0 else "🔴",
          "MACD 15m": "🟢" if macd_15m > 0 else "🔴",
          "MACD 1h": "🟢" if macd_1h > 0 else "🔴",
          "MACD 4h": "🟢" if macd_4h > 0 else "🔴",
          "RSI (1h)": round(rsi_actual, 1),
          "raw_df": df_1h,
      }
    except Exception:
      return None


async def ejecutar_escaneo(simbolos_custom=None):
  exchange_mexc = ccxt.mexc(
      {"enableRateLimit": True, "options": {"defaultType": "spot"}}
  )
  markets = await exchange_mexc.load_markets()

  if simbolos_custom:
    simbolos = [
        s
        for s in simbolos_custom
        if s in exchange_mexc.markets and exchange_mexc.markets[s]["active"]
    ]
  else:
    # Obtenemos los tickers para medir el volumen de 24h en MEXC
    tickers = await exchange_mexc.fetch_tickers()

    # Filtramos pares USDT activos y ordenamos por volumen de negociación (quoteVolume)
    pares_volumen = []
    for s, m in exchange_mexc.markets.items():
      if s.endswith("/USDT") and m["active"] and s in tickers:
        volumen_24h = tickers[s].get("quoteVolume", 0) or 0
        pares_volumen.append((s, volumen_24h))

    # Ordenar de mayor a menor volumen y tomar los top 250 (equivalente al ranking de Binance)
    pares_volumen.sort(key=lambda x: x[1], reverse=True)
    simbolos = [item[0] for item in pares_volumen[:250]]

  semaphore = asyncio.Semaphore(10)
  tareas = [analizar_simbolo(exchange_mexc, s, semaphore) for s in simbolos]
  resultados = await asyncio.gather(*tareas)
  await exchange_mexc.close()

  resultados_validos = [r for r in resultados if r is not None]
  resultados_validos.sort(key=lambda x: x["Prob_Subir_Num"], reverse=True)

  if simbolos_custom:
    return resultados_validos
  else:
    return [
        r
        for r in resultados_validos
        if r["Prob_Subir_Num"] >= 75 or (100 - r["Prob_Subir_Num"]) >= 75
    ]


# Botón de escaneo principal
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
  btn_escanear = st.button(
      "🔍 Iniciar Escaneo Pro", type="primary", use_container_width=True
  )

if btn_escanear:
  texto_spinner = (
      "Analizando Watchlist Personalizada..."
      if modo_escaneo == "Mi Watchlist Personalizada"
      else (
          "Filtrando los top 250 activos por volumen y analizando"
          " confluencia..."
      )
  )
  with st.spinner(texto_spinner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    destacados = loop.run_until_complete(
        ejecutar_escaneo(simbolos_personalizados)
    )

    if destacados:
      st.session_state["destacados"] = destacados
    else:
      st.warning(
          "No se encontraron criptomonedas cumpliendo los criterios en este"
          " momento."
      )

# Si hay resultados, mostramos métricas, tabla avanzada y gráficos
if "destacados" in st.session_state and st.session_state["destacados"]:
  st.markdown("---")

  total_encontrados = len(st.session_state["destacados"])
  alcistas = sum(
      1 for r in st.session_state["destacados"] if r["Prob_Subir_Num"] >= 75
  )

  m1, m2 = st.columns(2)
  with m1:
    st.metric(label="Activos de alta liquidez analizados", value=total_encontrados)
  with m2:
    st.metric(label="Con Tendencia Alcista Fuerte", value=alcistas)

  st.markdown("### 📋 Tabla de Resultados con Gestión de Riesgo")

  df_visible = pd.DataFrame(
      [
          {k: v for k, v in r.items() if k not in ["raw_df", "Prob_Subir_Num"]}
          for r in st.session_state["destacados"]
      ]
  )

  st.dataframe(
      df_visible,
      use_container_width=True,
      column_config={
          "Prob. Subir": st.column_config.ProgressColumn(
              "Prob. Subir",
              help="Porcentaje de probabilidad alcista con confluencia",
              format="%s",
              min_value=0,
              max_value=100,
          )
      },
  )

  st.markdown("---")
  st.subheader("📊 Gráfico Técnico Profesional (Estilo TradingView)")

  simbolos_disponibles = [r["Cripto"] for r in st.session_state["destacados"]]
  cripto_seleccionada = st.selectbox(
      "Selecciona una criptomoneda para inspeccionar:", simbolos_disponibles
  )

  crypto_data = next(
      r for r in st.session_state["destacados"] if r["Cripto"] == cripto_seleccionada
  )
  df_plot = crypto_data["raw_df"]

  # Cálculos para gráficos
  df_plot["sma"] = df_plot["close"].rolling(20).mean()
  df_plot["std"] = df_plot["close"].rolling(20).std()
  df_plot["upper"] = df_plot["sma"] + (2 * df_plot["std"])
  df_plot["lower"] = df_plot["sma"] - (2 * df_plot["std"])

  # MACD para el subgráfico inferior
  exp1 = df_plot["close"].ewm(span=12, adjust=False).mean()
  exp2 = df_plot["close"].ewm(span=26, adjust=False).mean()
  df_plot["macd"] = exp1 - exp2
  df_plot["signal"] = df_plot["macd"].ewm(span=9, adjust=False).mean()
  df_plot["hist"] = df_plot["macd"] - df_plot["signal"]

  df_plot["timestamp_dt"] = pd.to_datetime(df_plot["timestamp"], unit="ms")

  # Crear figura con 2 filas (Subplots)
  fig = make_subplots(
      rows=2,
      cols=1,
      shared_xaxes=True,
      vertical_spacing=0.03,
      row_heights=[0.7, 0.3],
  )

  # Fila 1: Velas y Bollinger
  fig.add_trace(
      go.Candlestick(
          x=df_plot["timestamp_dt"],
          open=df_plot["open"],
          high=df_plot["high"],
          low=df_plot["low"],
          close=df_plot["close"],
          name="Precio (1h)",
      ),
      row=1,
      col=1,
  )

  fig.add_trace(
      go.Scatter(
          x=df_plot["timestamp_dt"],
          y=df_plot["upper"],
          line=dict(color="rgba(250, 0, 0, 0.50)", width=1),
          name="Banda Superior",
      ),
      row=1,
      col=1,
  )
  fig.add_trace(
      go.Scatter(
          x=df_plot["timestamp_dt"],
          y=df_plot["sma"],
          line=dict(color="rgba(0, 100, 250, 0.6)", width=1),
          name="SMA 20",
      ),
      row=1,
      col=1,
  )
  fig.add_trace(
      go.Scatter(
          x=df_plot["timestamp_dt"],
          y=df_plot["lower"],
          line=dict(color="rgba(0, 250, 0, 0.50)", width=1),
          name="Banda Inferior",
          fill="tonexty",
          fillcolor="rgba(0, 250, 0, 0.03)",
      ),
      row=1,
      col=1,
  )

  # Fila 2: Histograma MACD
  colors = ["#00FF00" if val >= 0 else "#FF0000" for val in df_plot["hist"]]
  fig.add_trace(
      go.Bar(
          x=df_plot["timestamp_dt"],
          y=df_plot["hist"],
          marker_color=colors,
          name="MACD Histograma",
      ),
      row=2,
      col=1,
  )
  fig.add_trace(
      go.Scatter(
          x=df_plot["timestamp_dt"],
          y=df_plot["macd"],
          line=dict(color="#00ffff", width=1),
          name="MACD Line",
      ),
      row=2,
      col=1,
  )
  fig.add_trace(
      go.Scatter(
          x=df_plot["timestamp_dt"],
          y=df_plot["signal"],
          line=dict(color="#ff9900", width=1),
          name="Signal Line",
      ),
      row=2,
      col=1,
  )

  fig.update_layout(
      title=dict(
          text=f"<b>Análisis Técnico Avanzado: {cripto_seleccionada}</b>",
          font=dict(size=18),
      ),
      template="plotly_dark",
      height=650,
      xaxis_rangeslider_visible=False,
      legend=dict(
          orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
      ),
  )

  st.plotly_chart(fig, use_container_width=True)
