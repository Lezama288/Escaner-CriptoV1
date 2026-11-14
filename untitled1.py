import asyncio
import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Configuración de la página web
st.set_page_config(
    page_title="Terminal Cripto Pro - Dashboard Analítico",
    page_icon="📊",
    layout="wide",
)

# --- CSS PERSONALIZADO (ESTILO DASHBOARD PROFESIONAL CON TARJETAS KPI) ---
st.markdown(
    """
    <style>
    /* Fondo principal limpio y oscuro */
    .main { background-color: #0b0e14; }
    
    /* Encabezado tipo barra superior */
    .top-banner {
        background: linear-gradient(90deg, #1d5c63 0%, #2a7b84 100%);
        padding: 15px 25px;
        border-radius: 8px;
        color: white;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .top-banner h2 {
        margin: 0;
        font-size: 1.3rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    /* Tarjetas KPI de colores (Inspiradas en tu imagen) */
    .kpi-card {
        padding: 18px 20px;
        border-radius: 8px;
        color: white;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25);
        margin-bottom: 10px;
        transition: transform 0.2s ease;
    }
    .kpi-card:hover { transform: translateY(-3px); }
    
    .card-green { background: linear-gradient(135deg, #2e7d32 0%, #4caf50 100%); }
    .card-blue  { background: linear-gradient(135deg, #1565c0 0%, #29b6f6 100%); }
    .card-orange{ background: linear-gradient(135deg, #ef6c00 0%, #ffa726 100%); }
    .card-pink  { background: linear-gradient(135deg, #880e4f 0%, #d81b60 100%); }
    
    .kpi-title {
        font-size: 0.80rem;
        text-transform: uppercase;
        font-weight: 700;
        opacity: 0.9;
        margin-bottom: 6px;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 1.75rem;
        font-weight: 800;
        margin: 0;
    }
    .kpi-sub {
        font-size: 0.78rem;
        opacity: 0.85;
        margin-top: 4px;
    }

    /* Métricas secundarias minimalistas */
    .mini-stat {
        background-color: #151922;
        border: 1px solid #21262d;
        padding: 12px 16px;
        border-radius: 6px;
        text-align: center;
    }
    .mini-stat-label { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; }
    .mini-stat-val { color: #f0f6fc; font-size: 1.25rem; font-weight: 700; }

    /* Estilo de pestañas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #151922;
        padding: 6px;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        color: #c9d1d9;
        padding: 8px 18px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1d5c63 !important;
        color: white !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- BANNER SUPERIOR ---
st.markdown(
    """
    <div class="top-banner">
        <h2>📊 TERMINAL CRIPTO PRO — ESTADÍSTICAS Y FLUJO DE LIQUIDEZ (15m • 1h • 4h)</h2>
        <span style="font-size: 0.85rem; opacity: 0.9;">Exchange: MEXC Spot | Ref: BTC/USDT</span>
    </div>
""",
    unsafe_allow_html=True,
)

# --- BARRA LATERAL (CONFIGURACIÓN, BUSCADOR & WATCHLIST) ---
st.sidebar.header("⚙️ Panel de Control")
modo_escaneo = st.sidebar.radio(
    "Modo de Operación:",
    [
        "Buscar Moneda Específica (Seguimiento)",
        "Top Activos por Volumen (Alta Liquidez)",
        "Mi Watchlist Personalizada",
    ],
)

watchlist_default = (
    "BTC/USDT\nETH/USDT\nSOL/USDT\nXRP/USDT\nADA/USDT\nDOGE/USDT\nAVAX/USDT\nLINK/USDT\nPEPE/USDT\nRENDER/USDT"
)
simbolos_personalizados = None
moneda_buscada = None

if modo_escaneo == "Buscar Moneda Específica (Seguimiento)":
  st.sidebar.subheader("🔎 Buscador en Vivo")
  input_moneda = st.sidebar.text_input(
      "Ticker de la moneda (ej. SOL, ASTER, ETH):",
      value="SOL",
      help=(
          "Escribe el símbolo de la cripto. Siempre se analizará junto con"
          " BTC/USDT."
      ),
  )
  if input_moneda.strip():
    ticker_limpio = input_moneda.strip().upper()
    if "/" not in ticker_limpio:
      ticker_limpio = f"{ticker_limpio}/USDT"
    moneda_buscada = ticker_limpio
    simbolos_personalizados = [moneda_buscada]

elif modo_escaneo == "Mi Watchlist Personalizada":
  user_watchlist = st.sidebar.text_area(
      "Tu lista de seguimiento (PAR/USDT):",
      watchlist_default,
      height=150,
  )
  simbolos_personalizados = [
      s.strip().upper() for s in user_watchlist.split("\n") if s.strip()
  ]


# --- FUNCIONES DE CÁLCULO ---
def calcular_macd_hist(df):
  close = df["close"]
  exp1 = close.ewm(span=12, adjust=False).mean()
  exp2 = close.ewm(span=26, adjust=False).mean()
  macd_line = exp1 - exp2
  signal_line = macd_line.ewm(span=9, adjust=False).mean()
  hist = macd_line - signal_line
  return hist.iloc[-1]


def calcular_perfil_volumen_ponderado(df):
  """Calcula el Punto de Control (POC) ponderado por precio típico y volumen"""
  try:
    if len(df) == 0:
      return 0
    precio_min, precio_max = df["low"].min(), df["high"].max()
    if precio_min == precio_max:
      return df["close"].iloc[-1]

    bins = np.linspace(precio_min, precio_max, 20)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["bin"] = pd.cut(typical_price, bins=bins, include_lowest=True)

    vol_por_bin = df.groupby("bin", observed=False)["volume"].sum()
    if vol_por_bin.empty or vol_por_bin.max() == 0:
      return df["close"].iloc[-1]

    poc_bin = vol_por_bin.idxmax()
    poc_precio = (poc_bin.left + poc_bin.right) / 2
    return round(poc_precio, 4)
  except Exception:
    return df["close"].iloc[-1]


async def analizar_simbolo(exchange, symbol, semaphore):
  async with semaphore:
    try:
      v_15m, v_1h, v_4h = await asyncio.gather(
          exchange.fetch_ohlcv(symbol, timeframe="15m", limit=50),
          exchange.fetch_ohlcv(symbol, timeframe="1h", limit=50),
          exchange.fetch_ohlcv(symbol, timeframe="4h", limit=50),
      )

      if len(v_15m) < 35 or len(v_1h) < 35 or len(v_4h) < 35:
        return None

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
      precio_anterior = df_1h["close"].iloc[-2]
      cambio_1h = ((precio_actual - precio_anterior) / precio_anterior) * 100

      # Indicadores 1h
      close_1h = df_1h["close"]
      delta = close_1h.diff()
      gain = delta.where(delta > 0, 0).rolling(14).mean()
      loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
      rs = gain / loss
      rsi_series = 100 - (100 / (1 + rs))
      rsi_actual = rsi_series.iloc[-1] if not rsi_series.empty else 50.0

      sma_20 = close_1h.rolling(20).mean()
      std_20 = close_1h.rolling(20).std()
      upper = (sma_20 + (2 * std_20)).iloc[-1]
      lower = (sma_20 - (2 * std_20)).iloc[-1]
      sma = sma_20.iloc[-1]

      # MACD en las 3 Temporalidades
      macd_15m = calcular_macd_hist(df_15m)
      macd_1h = calcular_macd_hist(df_1h)
      macd_4h = calcular_macd_hist(df_4h)

      # Tendencia de Precios en las 3 Temporalidades
      alcista_15m = (
          precio_actual > df_15m["close"].rolling(20).mean().iloc[-1]
      )
      alcista_1h = precio_actual > sma
      alcista_4h = precio_actual > df_4h["close"].rolling(20).mean().iloc[-1]

      # Puntuación estructurada
      puntos_alcistas = 50
      puntos_alcistas += 8 if alcista_4h else -8
      puntos_alcistas += 6 if alcista_1h else -6
      puntos_alcistas += 4 if alcista_15m else -4

      puntos_alcistas += 12 if macd_4h > 0 else -12
      puntos_alcistas += 9 if macd_1h > 0 else -9
      puntos_alcistas += 6 if macd_15m > 0 else -6

      if not np.isnan(lower) and not np.isnan(upper):
        if precio_actual <= lower * 1.01:
          puntos_alcistas += 8
        elif precio_actual >= upper * 0.99:
          puntos_alcistas -= 8

      if not np.isnan(rsi_actual):
        if rsi_actual < 30:
          puntos_alcistas += 6
        elif rsi_actual > 70:
          puntos_alcistas -= 6

      prob_subir = max(0, min(100, int(puntos_alcistas)))
      conteo_tendencia = sum([alcista_15m, alcista_1h, alcista_4h])

      if conteo_tendencia == 3:
        tendencia_txt = "Alcista Fuerte"
      elif conteo_tendencia == 2:
        tendencia_txt = "Alcista Moderada"
      elif conteo_tendencia == 1:
        tendencia_txt = "Bajista Moderada"
      else:
        tendencia_txt = "Bajista Fuerte"

      # Gestión de Riesgo
      poc = calcular_perfil_volumen_ponderado(df_1h)
      stop_loss = round(min(lower * 0.99, poc * 0.98, precio_actual * 0.97), 4)
      riesgo = precio_actual - stop_loss
      if riesgo <= 0:
        stop_loss = round(precio_actual * 0.97, 4)
        riesgo = precio_actual - stop_loss

      take_profit = round(precio_actual + (riesgo * 2.0), 4)

      # Calcular proporción volumen comprador vs vendedor (aproximado por velas verdes/rojas)
      vol_compra = df_1h[df_1h["close"] >= df_1h["open"]]["volume"].sum()
      vol_venta = df_1h[df_1h["close"] < df_1h["open"]]["volume"].sum()

      return {
          "Cripto": symbol,
          "Precio ($)": round(precio_actual, 4),
          "Cambio_1h": round(cambio_1h, 2),
          "Tendencia (3T)": tendencia_txt,
          "POC (Vol)": poc,
          "Prob_Subir_Num": prob_subir,
          "Prob. Subir": f"{prob_subir}%",
          "Stop Loss ($)": stop_loss,
          "Take Profit ($)": take_profit,
          "MACD 15m": "🟢" if macd_15m > 0 else "🔴",
          "MACD 1h": "🟢" if macd_1h > 0 else "🔴",
          "MACD 4h": "🟢" if macd_4h > 0 else "🔴",
          "RSI (1h)": round(rsi_actual, 1),
          "vol_compra": vol_compra,
          "vol_venta": vol_venta,
          "raw_df": df_1h,
      }
    except Exception:
      return None


async def ejecutar_escaneo(simbolos_custom=None):
  exchange_mexc = ccxt.mexc(
      {"enableRateLimit": True, "options": {"defaultType": "spot"}}
  )
  try:
    await exchange_mexc.load_markets()

    if simbolos_custom:
      simbolos = [
          s
          for s in simbolos_custom
          if s in exchange_mexc.markets and exchange_mexc.markets[s]["active"]
      ]
      if "BTC/USDT" in exchange_mexc.markets and "BTC/USDT" not in simbolos:
        simbolos.insert(0, "BTC/USDT")
    else:
      tickers = await exchange_mexc.fetch_tickers()
      pares_volumen = []
      for s, m in exchange_mexc.markets.items():
        if s.endswith("/USDT") and m["active"] and s in tickers:
          volumen_24h = tickers[s].get("quoteVolume", 0) or 0
          pares_volumen.append((s, volumen_24h))

      pares_volumen.sort(key=lambda x: x[1], reverse=True)
      simbolos = [item[0] for item in pares_volumen[:100]]
      if "BTC/USDT" in simbolos:
        simbolos.remove("BTC/USDT")
      simbolos.insert(0, "BTC/USDT")

    semaphore = asyncio.Semaphore(8)
    tareas = [analizar_simbolo(exchange_mexc, s, semaphore) for s in simbolos]
    resultados = await asyncio.gather(*tareas)
    resultados_validos = [r for r in resultados if r is not None]

    def ordenar_btc_primero(x):
      if x["Cripto"] == "BTC/USDT":
        return (-1, -x["Prob_Subir_Num"])
      return (0, -x["Prob_Subir_Num"])

    resultados_validos.sort(key=ordenar_btc_primero)
    return resultados_validos

  finally:
    await exchange_mexc.close()


# --- BOTÓN DE EJECUCIÓN ---
texto_boton = (
    f"🔄 Actualizar Datos de {moneda_buscada}"
    if modo_escaneo == "Buscar Moneda Específica (Seguimiento)"
    and moneda_buscada
    else "🔍 Ejecutar Escáner de Mercado"
)

if st.sidebar.button(texto_boton, type="primary", use_container_width=True):
  if (
      modo_escaneo == "Buscar Moneda Específica (Seguimiento)"
      and not moneda_buscada
  ):
    st.warning("Por favor, escribe el nombre de una moneda en el buscador.")
  else:
    with st.spinner("Sincronizando datos con MEXC..."):
      try:
        loop = asyncio.get_event_loop()
      except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

      destacados = loop.run_until_complete(
          ejecutar_escaneo(simbolos_personalizados)
      )

      if destacados:
        if modo_escaneo == "Buscar Moneda Específica (Seguimiento)":
          encontrada = any(r["Cripto"] == moneda_buscada for r in destacados)
          if not encontrada:
            st.error(f"❌ El par **{moneda_buscada}** no está activo en MEXC.")
        st.session_state["destacados"] = destacados
        st.session_state["ultima_buscada"] = moneda_buscada
      else:
        st.warning("No se obtuvieron datos del exchange.")

# --- RENDERIZADO DEL DASHBOARD ---
if "destacados" in st.session_state and st.session_state["destacados"]:
  simbolos_disponibles = [r["Cripto"] for r in st.session_state["destacados"]]

  index_default = 0
  if (
      st.session_state.get("ultima_buscada")
      and st.session_state["ultima_buscada"] in simbolos_disponibles
  ):
    index_default = simbolos_disponibles.index(
        st.session_state["ultima_buscada"]
    )

  # Selector superior estilo barra de filtros
  col_sel, col_info = st.columns([2, 3])
  with col_sel:
    cripto_seleccionada = st.selectbox(
        "📌 Activo en Inspección Detallada:",
        simbolos_disponibles,
        index=index_default,
    )

  crypto_data = next(
      r
      for r in st.session_state["destacados"]
      if r["Cripto"] == cripto_seleccionada
  )
  btc_data = next(
      (r for r in st.session_state["destacados"] if r["Cripto"] == "BTC/USDT"),
      None,
  )

  # 1. TARJETAS KPI SUPERIORES DE COLORES (Igual que el diseño de referencia)
  k1, k2, k3, k4 = st.columns(4)

  with k1:
    signo = "+" if crypto_data["Cambio_1h"] >= 0 else ""
    st.markdown(
        f"""
        <div class="kpi-card card-green">
            <div class="kpi-title">💰 PRECIO ACTUAL ({crypto_data['Cripto']})</div>
            <div class="kpi-value">${crypto_data['Precio ($)']}</div>
            <div class="kpi-sub">Variación 1h: {signo}{crypto_data['Cambio_1h']}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

  with k2:
    st.markdown(
        f"""
        <div class="kpi-card card-
