"""
AbejaNet — 00_generar_datos.py
===============================================================
Genera un dataset sintético de lecturas de sensores IoT de
colmenas, basado en la simulación del archivo original:
    backend/generate_mock_data.js

El dataset se genera limpio primero y luego se le introducen
intencionalmente problemas de calidad para que el pipeline de
limpieza (02_de_limpieza_pipeline.py) tenga qué corregir.

Salida: data/raw/lecturas_crudas.csv
===============================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import math

np.random.seed(42)

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE LA SIMULACIÓN
# ──────────────────────────────────────────────────────────────

DIAS             = 30
LECTURAS_POR_HORA = 4           # cada 15 minutos
INTERVALO_MIN    = 60 // LECTURAS_POR_HORA
FECHA_INICIO     = datetime(2025, 5, 15, 0, 0, 0)

# Tres colmenas basadas en los datos reales del proyecto
COLMENAS = [
    {
        "sensor_id":       1,
        "mac_address":     "AA:BB:CC:11:22:33",
        "tipo_sensor":     "Temperatura/Humedad",
        "colmena_id":      1,
        "colmena_nombre":  "Colmena Alfa Ppal",
        "apiario_nombre":  "Apiario Principal",
        "ubicacion":       "19.4326 N, 99.1332 W",
        "tiene_peso":      False,   # Sensor de T/H no mide peso
    },
    {
        "sensor_id":       2,
        "mac_address":     "AA:BB:CC:11:22:44",
        "tipo_sensor":     "Multisensor",
        "colmena_id":      2,
        "colmena_nombre":  "Colmena Gamma Ppal",
        "apiario_nombre":  "Apiario Principal",
        "ubicacion":       "19.4326 N, 99.1332 W",
        "tiene_peso":      True,
    },
    {
        "sensor_id":       3,
        "mac_address":     "A2:04:2A:B9:C1:D9",
        "tipo_sensor":     "Multisensor",
        "colmena_id":      3,
        "colmena_nombre":  "Colmena Beta Lab",
        "apiario_nombre":  "Apiario Laboratorio",
        "ubicacion":       "20.6597 N, 103.3496 W",
        "tiene_peso":      True,
    },
]

# ──────────────────────────────────────────────────────────────
# FUNCIONES DE SIMULACIÓN
# Lógica basada en generate_mock_data.js (líneas 36-62)
# ──────────────────────────────────────────────────────────────

def simular_temperatura(fecha: datetime, offset: float = 0.0) -> float:
    """
    Ciclo coseno diario: mínimo en madrugada, máximo a media tarde.
    base=20°C, variación amplitud=14°C → rango aprox. 13-34°C
    """
    hora = fecha.hour + fecha.minute / 60.0
    temp = 20.0 + (14.0 / 2.0) * (1 - math.cos((hora / 24.0) * 2 * math.pi))
    return round(temp + offset + float(np.random.uniform(-0.8, 0.8)), 2)


def simular_humedad(temperatura: float) -> float:
    """Correlación inversa con temperatura. Rango biológico: 40-95%."""
    humedad = 75.0 - (temperatura - 20.0) * 1.8 + float(np.random.uniform(-2.5, 2.5))
    return round(float(np.clip(humedad, 40.0, 95.0)), 2)


def simular_peso(dia: int, peso_base: float) -> float:
    """Tendencia de crecimiento lineal de ~0.08 kg/día + ruido."""
    return round(peso_base + dia * 0.08 + float(np.random.uniform(-0.06, 0.06)), 2)


def simular_sonido(fecha: datetime) -> float:
    """
    Actividad diurna (07-20h): ~60-70 dB.
    Noche: ~44-54 dB.
    """
    hora = fecha.hour
    es_dia = 7 <= hora < 20
    base = 60.0 if es_dia else 44.0
    return round(base + float(np.random.uniform(0.0, 10.0)), 2)


def simular_lluvia() -> bool:
    """5% de probabilidad de lluvia por lectura."""
    return bool(np.random.random() < 0.05)

# ──────────────────────────────────────────────────────────────
# GENERACIÓN DEL DATASET LIMPIO
# ──────────────────────────────────────────────────────────────

print("=" * 60)
print("  AbejaNet — Generador de Dataset Sintético")
print("=" * 60)
print(f"\n  Periodo: {FECHA_INICIO.strftime('%Y-%m-%d')} + {DIAS} días")
print(f"  Lecturas por hora: {LECTURAS_POR_HORA} (c/{INTERVALO_MIN} min)")
print(f"  Colmenas simuladas: {len(COLMENAS)}")
print(f"  Registros esperados por colmena: {DIAS * 24 * LECTURAS_POR_HORA}")

filas = []
offsets_temperatura = {1: 0.0, 2: 1.2, 3: -0.5}  # Cada colmena en distinto microclima
pesos_base          = {1: 0.0, 2: 14.5, 3: 15.0}

for col in COLMENAS:
    fecha    = FECHA_INICIO
    offset_t = offsets_temperatura[col["sensor_id"]]
    peso_b   = pesos_base[col["sensor_id"]]

    for dia in range(DIAS):
        for _ in range(24 * LECTURAS_POR_HORA):
            temp   = simular_temperatura(fecha, offset_t)
            hum    = simular_humedad(temp)
            peso   = simular_peso(dia, peso_b) if col["tiene_peso"] else np.nan
            sonido = simular_sonido(fecha)
            lluvia = simular_lluvia()

            filas.append({
                "sensor_id":      col["sensor_id"],
                "mac_address":    col["mac_address"],
                "tipo_sensor":    col["tipo_sensor"],
                "colmena_id":     col["colmena_id"],
                "colmena_nombre": col["colmena_nombre"],
                "apiario_nombre": col["apiario_nombre"],
                "ubicacion":      col["ubicacion"],
                "temperatura":    temp,
                "humedad":        hum,
                "peso":           peso,
                "sonido":         sonido,
                "lluvia":         lluvia,
                "fecha_registro": fecha,
            })
            fecha += timedelta(minutes=INTERVALO_MIN)

df_limpio = pd.DataFrame(filas)
total_limpio = len(df_limpio)
print(f"\n  ✔ Dataset limpio generado: {total_limpio} registros")

# ──────────────────────────────────────────────────────────────
# INTRODUCCIÓN DE PROBLEMAS DE CALIDAD
# ──────────────────────────────────────────────────────────────

print("\n  Introduciendo problemas de calidad...")
df = df_limpio.copy()

# 1. Valores nulos aleatorios en columnas numéricas
for columna, pct in [("humedad", 0.05), ("temperatura", 0.04), ("sonido", 0.03)]:
    idx = df.sample(frac=pct, random_state=42).index
    df.loc[idx, columna] = np.nan
    print(f"  [Nulos] {columna}: {len(idx)} celdas → NaN ({pct*100:.0f}%)")

# 2. Outliers de temperatura: valores físicamente imposibles
n_outliers_temp = int(total_limpio * 0.01)
idx_hot  = df.sample(n=n_outliers_temp // 2, random_state=7).index
idx_cold = df.sample(n=n_outliers_temp // 2, random_state=8).index
df.loc[idx_hot,  "temperatura"] = np.round(np.random.uniform(48, 57, n_outliers_temp // 2), 2)
df.loc[idx_cold, "temperatura"] = np.round(np.random.uniform(-4,  1, n_outliers_temp // 2), 2)
print(f"  [Outliers] temperatura: {n_outliers_temp} valores fuera de rango ([−4,1] y [48,57])")

# 3. Outliers de humedad: valores > 100%
n_outliers_hum = int(total_limpio * 0.008)
idx_hum = df.sample(n=n_outliers_hum, random_state=11).index
df.loc[idx_hum, "humedad"] = np.round(np.random.uniform(101, 112, n_outliers_hum), 2)
print(f"  [Outliers] humedad: {n_outliers_hum} valores > 100%")

# 4. Filas duplicadas exactas
n_dup = int(total_limpio * 0.015)
filas_dup = df.sample(n=n_dup, random_state=99)
df = pd.concat([df, filas_dup], ignore_index=True)
print(f"  [Duplicados] {n_dup} filas duplicadas añadidas")

# 5. Formato incorrecto en lluvia: "si"/"no" como string en lugar de bool
idx_fmt = df.sample(frac=0.04, random_state=55).index
df["lluvia"] = df["lluvia"].astype(object)          # permitir tipos mixtos
df.loc[idx_fmt, "lluvia"] = df.loc[idx_fmt, "lluvia"].map(
    lambda x: "si" if str(x).lower() in ("true", "1", "si") else "no"
)
print(f"  [Formato] lluvia: {len(idx_fmt)} filas convertidas a string 'si'/'no'")

# 6. sensor_id nulo en algunos registros (registro huérfano)
n_sin_sensor = int(total_limpio * 0.008)
idx_no_sid = df.sample(n=n_sin_sensor, random_state=22).index
df.loc[idx_no_sid, "sensor_id"] = np.nan
print(f"  [Huérfanos] sensor_id: {n_sin_sensor} filas sin ID de sensor")

# Mezclar orden para simular inserción real
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# ──────────────────────────────────────────────────────────────
# RESUMEN FINAL
# ──────────────────────────────────────────────────────────────

print(f"\n{'─'*60}")
print(f"  RESUMEN DEL DATASET GENERADO")
print(f"{'─'*60}")
print(f"  Total de filas           : {len(df)}")
print(f"  Registros originales     : {total_limpio}")
print(f"  Filas duplicadas         : {n_dup}")
print(f"\n  Nulos por columna:")
for col_name in ["sensor_id", "temperatura", "humedad", "sonido", "peso"]:
    nulos = df[col_name].isna().sum()
    pct   = nulos / len(df) * 100
    print(f"    {col_name:<18}: {nulos:>5} ({pct:.2f}%)")
print(f"\n  Valores únicos en 'lluvia': {df['lluvia'].unique()[:6]}")

# ──────────────────────────────────────────────────────────────
# GUARDAR
# ──────────────────────────────────────────────────────────────

os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/clean", exist_ok=True)

ruta = os.path.join("data", "raw", "lecturas_crudas.csv")
df.to_csv(ruta, index=False, encoding="utf-8")

print(f"\n  ✅ Guardado en : {ruta}")
print(f"  Columnas       : {list(df.columns)}")
print(f"  Shape          : {df.shape}")
