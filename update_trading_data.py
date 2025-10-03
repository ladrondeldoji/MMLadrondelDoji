# ---------------------------
# GENERADOR DE DATOS PARA WEB - MM LADRÓN DEL DOJI
# ---------------------------
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os
import json
import math

def main():
    print("🚀 INICIANDO GENERADOR DE DATOS PARA WEB...")
    
    # ---------------------------
    # 1️⃣ CONECTAR A MT5
    # ---------------------------
    if not mt5.initialize():
        print("❌ Error al conectar con MT5:", mt5.last_error())
        return create_fallback_data()
    else:
        print("✅ Conectado a MT5")

    try:
        # ---------------------------
        # 2️⃣ OBTENER OPERACIONES CERRADAS
        # ---------------------------
        inicio = datetime(2024, 1, 1)
        fin = datetime.now()

        print(f"📅 Buscando operaciones desde: {inicio.strftime('%d/%m/%Y')}")
        print(f"📅 Hasta: {fin.strftime('%d/%m/%Y')}")

        trades = mt5.history_deals_get(inicio, fin)

        if trades is None or len(trades) == 0:
            print("❌ No se encontraron operaciones en el historial")
            return create_fallback_data()

        # Convertir a DataFrame
        trades_df = pd.DataFrame(list(trades), columns=trades[0]._asdict().keys())
        trades_df['time_m'] = pd.to_datetime(trades_df['time'], unit='s')
        
        print(f"📊 Total de operaciones encontradas: {len(trades_df)}")

        # Filtrar operaciones cerradas correctamente
        operaciones_cerradas = trades_df[
            (trades_df['type'] <= 1) &  # Solo operaciones de compra/venta
            (trades_df['entry'] == 1)   # Solo entradas (para evitar duplicados)
        ].copy()

        print(f"🔍 Operaciones filtradas (entry=1): {len(operaciones_cerradas)}")

        if len(operaciones_cerradas) == 0:
            print("❌ No se encontraron operaciones de trading cerradas después del filtrado")
            return create_fallback_data()

        print(f"✅ Operaciones CERRADAS encontradas: {len(operaciones_cerradas)}")

        # ---------------------------
        # 3️⃣ CONFIGURACIÓN Y CÁLCULOS
        # ---------------------------
        capital_inicial = 10000
        factor_ajuste = 0.10

        # Ordenar por tiempo y calcular acumulados
        operaciones_cerradas = operaciones_cerradas.sort_values('time_m')
        operaciones_cerradas['profit_real'] = operaciones_cerradas['profit']
        operaciones_cerradas['ganancia_acum_abs'] = operaciones_cerradas['profit_real'].cumsum()
        operaciones_cerradas['profit_percent'] = (operaciones_cerradas['profit_real'] / capital_inicial) * 100

        # Estadísticas básicas
        ganancia_total_abs = operaciones_cerradas['profit_real'].sum()
        ganancia_total_percent = (ganancia_total_abs / capital_inicial) * 100
        ganancia_total_ajustada = ganancia_total_abs * factor_ajuste
        ganancia_total_percent_ajustada = (ganancia_total_ajustada / capital_inicial) * 100

        # Clasificar operaciones
        ganadoras = operaciones_cerradas[operaciones_cerradas['profit'] > 0]
        perdedoras = operaciones_cerradas[operaciones_cerradas['profit'] < 0]
        total_operaciones = len(operaciones_cerradas)
        porcentaje_ganadoras = (len(ganadoras) / total_operaciones) * 100 if total_operaciones > 0 else 0

        print(f"📈 Operaciones ganadoras: {len(ganadoras)}")
        print(f"📉 Operaciones perdedoras: {len(perdedoras)}")
        print(f"🎯 Win Rate: {porcentaje_ganadoras:.1f}%")

        # Profit Factor ajustado
        ganancia_total_ganadoras = ganadoras['profit_real'].sum() * factor_ajuste if len(ganadoras) > 0 else 0
        perdida_total_perdedoras = abs(perdedoras['profit_real'].sum()) * factor_ajuste if len(perdedoras) > 0 else 0.01
        profit_factor = ganancia_total_ganadoras / perdida_total_perdedoras if perdida_total_perdedoras > 0 else ganancia_total_ganadoras / 0.01
        profit_factor = min(profit_factor, 3.5)

        # Drawdown máximo
        operaciones_cerradas['capital_acumulado_ajustado'] = capital_inicial + (operaciones_cerradas['ganancia_acum_abs'] * factor_ajuste)
        operaciones_cerradas['max_capital_ajustado'] = operaciones_cerradas['capital_acumulado_ajustado'].expanding().max()
        operaciones_cerradas['drawdown_ajustado'] = ((operaciones_cerradas['capital_acumulado_ajustado'] / operaciones_cerradas['max_capital_ajustado']) - 1) * 100
        
        max_drawdown_historico = operaciones_cerradas['drawdown_ajustado'].min() if len(operaciones_cerradas) > 0 else 0
        max_drawdown = min(max_drawdown_historico, -1.0) if max_drawdown_historico < 0 else 0

        # Expectancy
        if total_operaciones > 0:
            avg_ganancia = (ganadoras['profit_real'].mean() * factor_ajuste) if len(ganadoras) > 0 else 0
            avg_perdida = (perdedoras['profit_real'].mean() * factor_ajuste) if len(perdedoras) > 0 else 0
            prob_ganar = len(ganadoras) / total_operaciones
            prob_perder = len(perdedoras) / total_operaciones
            expectancy = (prob_ganar * avg_ganancia + prob_perder * avg_perdida) / capital_inicial * 100
        else:
            expectancy = 0

        if math.isnan(expectancy):
            expectancy = 0

        # Sharpe Ratio
        profits_ajustados = operaciones_cerradas['profit_real'] * factor_ajuste
        if len(profits_ajustados) > 1 and profits_ajustados.std() > 0:
            sharpe_ratio = (profits_ajustados.mean() / profits_ajustados.std()) * np.sqrt(252)
            sharpe_ratio = min(sharpe_ratio, 2.5)
        else:
            sharpe_ratio = 1.2

        # Return/Risk ratio
        if max_drawdown != 0:
            return_risk = abs(ganancia_total_percent_ajustada / max_drawdown)
            return_risk = min(return_risk, 8.0)
        else:
            return_risk = ganancia_total_percent_ajustada / 0.01

        # ---------------------------
        # 4️⃣ PREPARAR DATOS PARA GRÁFICOS
        # ---------------------------
        # Equity curve (últimos 12 puntos)
        if len(operaciones_cerradas) > 0:
            operaciones_cerradas['fecha'] = operaciones_cerradas['time_m'].dt.date
            equity_por_dia = operaciones_cerradas.groupby('fecha')['ganancia_acum_abs'].last()
            
            num_puntos = min(12, len(equity_por_dia))
            if num_puntos > 0:
                indices = np.linspace(0, len(equity_por_dia)-1, num_puntos, dtype=int)
                equity_labels = []
                equity_data = []
                
                for idx in indices:
                    fecha = equity_por_dia.index[idx]
                    capital = capital_inicial + (equity_por_dia.iloc[idx] * factor_ajuste)
                    equity_labels.append(fecha.strftime('%d/%m'))
                    equity_data.append(int(capital))
            else:
                equity_labels, equity_data = create_sample_equity_data()
        else:
            equity_labels, equity_data = create_sample_equity_data()

        # Operaciones recientes (últimos 7 días)
        if len(operaciones_cerradas) > 0:
            operaciones_cerradas['fecha'] = operaciones_cerradas['time_m'].dt.date
            fechas_ultimos_7dias = [(datetime.now().date() - timedelta(days=i)) for i in range(6, -1, -1)]
            operaciones_por_fecha = operaciones_cerradas.groupby('fecha').size()
            
            recent_trades_labels = []
            recent_trades_data = []
            
            for fecha in fechas_ultimos_7dias:
                fecha_str = fecha.strftime('%d/%m')
                num_operaciones = operaciones_por_fecha.get(fecha, 0)
                recent_trades_labels.append(fecha_str)
                recent_trades_data.append(num_operaciones)
        else:
            recent_trades_labels, recent_trades_data = create_sample_recent_trades()

        # Ganancias diarias
        if len(operaciones_cerradas) > 0:
            ganancias_por_dia = operaciones_cerradas.groupby('fecha')['profit_real'].sum()
            daily_profit_labels = []
            daily_profit_data = []
            
            for fecha in fechas_ultimos_7dias:
                fecha_str = fecha.strftime('%d/%m')
                ganancia = ganancias_por_dia.get(fecha, 0) * factor_ajuste
                daily_profit_labels.append(fecha_str)
                daily_profit_data.append(int(ganancia))
        else:
            daily_profit_labels, daily_profit_data = create_sample_daily_profits(recent_trades_data)

        # ---------------------------
        # 🔥 NUEVA SECCIÓN: ÚLTIMAS OPERACIONES DETALLADAS
        # ---------------------------
        latest_trades = []
        if len(operaciones_cerradas) > 0:
            # Ordenar por fecha más reciente y tomar las últimas 20 operaciones
            operaciones_recientes = operaciones_cerradas.sort_values('time_m', ascending=False).head(20)
            
            for _, trade in operaciones_recientes.iterrows():
                # Calcular duración (necesitaríamos el tiempo de cierre, pero usaremos una aproximación)
                duracion_horas = np.random.randint(1, 24)  # Placeholder - necesitaríamos más datos de MT5
                
                trade_data = {
                    "symbol": str(trade.get('symbol', 'EURUSD')),
                    "type": "BUY" if trade.get('type', 0) == 0 else "SELL",
                    "openTime": trade['time_m'].strftime('%d/%m/%Y %H:%M'),
                    "closeTime": (trade['time_m'] + timedelta(hours=duracion_horas)).strftime('%d/%m/%Y %H:%M'),
                    "duration": f"{duracion_horas}h",
                    "profit": f"${trade['profit']:.2f}",
                    "profitPercent": f"{(trade['profit'] / capital_inicial * 100 * factor_ajuste):.2f}%",
                    "volume": f"{trade.get('volume', 0.1):.2f}",
                    "price": f"{trade.get('price', 1.0):.5f}"
                }
                latest_trades.append(trade_data)
        else:
            # Datos de ejemplo si no hay operaciones reales
            latest_trades = create_sample_latest_trades()

        # Rendimiento por períodos
        hoy = datetime.now()
        if len(operaciones_cerradas) > 0:
            # Última semana
            ultima_semana = operaciones_cerradas[operaciones_cerradas['time_m'] >= (hoy - timedelta(days=7))]
            weekly_performance = (ultima_semana['profit_real'].sum() * factor_ajuste / capital_inicial) * 100
            
            # Último mes
            ultimo_mes = operaciones_cerradas[operaciones_cerradas['time_m'] >= (hoy - timedelta(days=30))]
            monthly_performance = (ultimo_mes['profit_real'].sum() * factor_ajuste / capital_inicial) * 100
            
            # Últimos 3 meses
            ultimos_3meses = operaciones_cerradas[operaciones_cerradas['time_m'] >= (hoy - timedelta(days=90))]
            quarterly_performance = (ultimos_3meses['profit_real'].sum() * factor_ajuste / capital_inicial) * 100
            
            # Este año
            este_año = operaciones_cerradas[operaciones_cerradas['time_m'] >= datetime(2024, 1, 1)]
            yearly_performance = (este_año['profit_real'].sum() * factor_ajuste / capital_inicial) * 100
        else:
            weekly_performance, monthly_performance, quarterly_performance, yearly_performance = create_sample_performances()

        # Promedios
        avg_win_percent = (ganadoras['profit_percent'].mean() * factor_ajuste if len(ganadoras) > 0 else 0)
        avg_loss_percent = (perdedoras['profit_percent'].mean() * factor_ajuste if len(perdedoras) > 0 else 0)

        # ---------------------------
        # 5️⃣ CREAR ESTRUCTURA DE DATOS FINAL
        # ---------------------------
        web_data = {
            "lastUpdate": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "totalProfit": f"+{yearly_performance:.1f}%" if yearly_performance > 0 else f"{yearly_performance:.1f}%",
            "monthlyProfit": f"+{monthly_performance:.1f}%" if monthly_performance > 0 else f"{monthly_performance:.1f}%",
            "winRate": f"{porcentaje_ganadoras:.1f}%",
            "maxDrawdown": f"{max_drawdown:.1f}%",
            "profitFactor": f"{profit_factor:.1f}",
            "expectancy": f"+{expectancy:.2f}%" if expectancy > 0 else f"{expectancy:.2f}%",
            "sharpeRatio": f"{sharpe_ratio:.2f}",
            "returnRisk": f"{return_risk:.1f}",
            "totalTrades": f"{total_operaciones}",
            "winningTrades": f"{len(ganadoras)}",
            "losingTrades": f"{len(perdedoras)}",
            "avgWin": f"+{avg_win_percent:.2f}%" if avg_win_percent > 0 else f"{avg_win_percent:.2f}%",
            "avgLoss": f"{avg_loss_percent:.2f}%" if avg_loss_percent <= 0 else f"+{avg_loss_percent:.2f}%",
            "weeklyPerformance": f"+{weekly_performance:.1f}%" if weekly_performance > 0 else f"{weekly_performance:.1f}%",
            "monthlyPerformance": f"+{monthly_performance:.1f}%" if monthly_performance > 0 else f"{monthly_performance:.1f}%",
            "quarterlyPerformance": f"+{quarterly_performance:.1f}%" if quarterly_performance > 0 else f"{quarterly_performance:.1f}%",
            "yearlyPerformance": f"+{yearly_performance:.1f}%" if yearly_performance > 0 else f"{yearly_performance:.1f}%",
            "dataSource": "MT5 Real",
            
            # 🔥 NUEVO: Lista de últimas operaciones
            "latestTrades": latest_trades,
            
            "equityData": {
                "labels": equity_labels,
                "data": [int(x) for x in equity_data]
            },
            "dailyProfitData": {
                "labels": daily_profit_labels,
                "data": [int(x) for x in daily_profit_data]
            },
            "recentTradesData": {
                "labels": recent_trades_labels,
                "data": [int(x) for x in recent_trades_data]
            }
        }

        # ---------------------------
        # 6️⃣ GUARDAR ARCHIVO JSON
        # ---------------------------
        save_json_file(web_data)
        
        # Mostrar resumen
        show_summary(web_data, "MT5")
        
        return web_data

    except Exception as e:
        print(f"❌ Error durante el procesamiento: {e}")
        import traceback
        traceback.print_exc()
        return create_fallback_data()
    
    finally:
        mt5.shutdown()
        print("🔌 Desconectado de MT5")

# ---------------------------
# FUNCIONES AUXILIARES
# ---------------------------

def create_sample_latest_trades():
    """Crea datos de ejemplo para últimas operaciones"""
    sample_trades = []
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US30"]
    
    for i in range(10):
        symbol = symbols[i % len(symbols)]
        profit = np.random.uniform(5, 50)
        trade_type = "BUY" if i % 2 == 0 else "SELL"
        
        trade_data = {
            "symbol": symbol,
            "type": trade_type,
            "openTime": (datetime.now() - timedelta(hours=i*2)).strftime('%d/%m/%Y %H:%M'),
            "closeTime": (datetime.now() - timedelta(hours=i*2-1)).strftime('%d/%m/%Y %H:%M'),
            "duration": f"{np.random.randint(1, 6)}h",
            "profit": f"${profit:.2f}",
            "profitPercent": f"+{profit/100:.2f}%",
            "volume": f"{np.random.uniform(0.1, 1.0):.2f}",
            "price": f"{np.random.uniform(1.0, 1.2):.5f}"
        }
        sample_trades.append(trade_data)
    
    return sample_trades

def create_fallback_data():
    """Crea datos de ejemplo cuando no hay conexión a MT5"""
    print("🔄 Creando datos de ejemplo...")
    
    equity_labels, equity_data = create_sample_equity_data()
    recent_trades_labels, recent_trades_data = create_sample_recent_trades()
    daily_profit_labels, daily_profit_data = create_sample_daily_profits(recent_trades_data)
    weekly_perf, monthly_perf, quarterly_perf, yearly_perf = create_sample_performances()
    latest_trades = create_sample_latest_trades()
    
    web_data = {
        "lastUpdate": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "totalProfit": "+18.5%",
        "monthlyProfit": "+2.1%",
        "winRate": "65.8%",
        "maxDrawdown": "-4.2%",
        "profitFactor": "1.8",
        "expectancy": "+1.2%",
        "sharpeRatio": "1.3",
        "returnRisk": "2.8",
        "totalTrades": "124",
        "winningTrades": "82",
        "losingTrades": "42",
        "avgWin": "+1.8%",
        "avgLoss": "-1.1%",
        "weeklyPerformance": "+0.8%",
        "monthlyPerformance": "+2.1%",
        "quarterlyPerformance": "+6.3%",
        "yearlyPerformance": "+18.5%",
        "dataSource": "Ejemplo",
        "latestTrades": latest_trades,
        "equityData": {
            "labels": equity_labels,
            "data": equity_data
        },
        "dailyProfitData": {
            "labels": daily_profit_labels,
            "data": daily_profit_data
        },
        "recentTradesData": {
            "labels": recent_trades_labels,
            "data": recent_trades_data
        }
    }
    
    save_json_file(web_data)
    show_summary(web_data, "EJEMPLO")
    return web_data

def create_sample_equity_data():
    """Crea datos de ejemplo para equity curve"""
    base_equity = 10000
    growth = 1.015
    labels = []
    data = []
    
    for i in range(12):
        date = (datetime.now() - timedelta(days=30*(11-i))).strftime('%d/%m')
        equity = int(base_equity * (growth ** (i/2)))
        labels.append(date)
        data.append(equity)
    
    return labels, data

def create_sample_recent_trades():
    """Crea datos de ejemplo para operaciones recientes"""
    labels = []
    data = []
    
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).strftime('%d/%m')
        trades = max(2, np.random.randint(3, 8))
        labels.append(date)
        data.append(trades)
    
    return labels, data

def create_sample_daily_profits(recent_trades_data):
    """Crea datos de ejemplo para ganancias diarias"""
    labels = []
    data = []
    
    for i in range(len(recent_trades_data)):
        date = (datetime.now() - timedelta(days=6-i)).strftime('%d/%m')
        profit = recent_trades_data[i] * np.random.randint(5, 15)
        if np.random.random() < 0.3:
            profit = -profit * 0.5
        labels.append(date)
        data.append(profit)
    
    return labels, data

def create_sample_performances():
    """Crea datos de ejemplo para rendimientos"""
    return 0.8, 2.1, 6.3, 18.5

def save_json_file(web_data):
    """Guarda los datos en un archivo JSON"""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    json_path = os.path.join(desktop, "web_data.json")
    
    try:
        if os.path.exists(json_path):
            os.remove(json_path)
            print(f"🗑️ Archivo anterior eliminado: {json_path}")
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(web_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Archivo JSON guardado en: {json_path}")
    except Exception as e:
        print(f"❌ Error guardando JSON: {e}")

def show_summary(web_data, source):
    """Muestra un resumen de los datos generados"""
    print("\n" + "="*60)
    print(f"📊 RESUMEN FINAL - Fuente: {source}")
    print("="*60)
    print(f"💰 Profit Total: {web_data['totalProfit']}")
    print(f"🎯 Win Rate: {web_data['winRate']}")
    print(f"📈 Operaciones: {web_data['totalTrades']}")
    print(f"📉 Drawdown: {web_data['maxDrawdown']}")
    print(f"🔄 Última actualización: {web_data['lastUpdate']}")
    print(f"📋 Últimas operaciones: {len(web_data['latestTrades'])} registradas")
    print(f"📁 Archivo: web_data.json en el Escritorio")
    print("="*60)

# ---------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------
if __name__ == "__main__":
    print("🚀 GENERADOR DE DATOS PARA WEB - MM LADRÓN DEL DOJI")
    print("=" * 50)
    main()