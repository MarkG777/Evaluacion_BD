"""
AbejaNet — 02_de_limpieza_pipeline.py
===============================================================
DE — Evidencia de Desempeño: Reporte del Proceso de Limpieza

Aplica técnicas de limpieza paso a paso sobre el dataset crudo
generado por 00_generar_datos.py, mostrando evidencia del
"antes y después" de cada transformación.

Entrada : data/raw/lecturas_crudas.csv
Salidas :
    data/clean/lecturas_limpias.csv
    data/clean/log_limpieza.txt
===============================================================
EJECUTAR DESDE: practica_preprocesamiento/
    python 02_de_limpieza_pipeline.py
===============================================================
"""

import pandas as pd
import numpy as np
import os
import sys
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────

RUTA_CRUDO = os.path.join("data", "raw", "lecturas_crudas.csv")
RUTA_LIMPIO = os.path.join("data", "clean", "lecturas_limpias.csv")
RUTA_LOG    = os.path.join("data", "clean", "log_limpieza.txt")

os.makedirs("data/clean", exist_ok=True)

# Redirigir salida también a archivo de log
class Tee:
    """Escribe simultáneamente en stdout y en un archivo."""
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

log_file = open(RUTA_LOG, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_file)

# ──────────────────────────────────────────────────────────────
# UTILIDADES DE EVIDENCIA
# ──────────────────────────────────────────────────────────────

def sep(titulo: str, ancho: int = 65):
    linea = "=" * ancho
    print(f"\n{linea}")
    print(f"  {titulo}")
    print(linea)

def antes_despues(df_a: pd.DataFrame, df_d: pd.DataFrame, etiqueta: str):
    delta_filas = len(df_a) - len(df_d)
    delta_nulos = df_a.isna().sum().sum() - df_d.isna().sum().sum()
    print(f"\n  ── Resultado: {etiqueta} ──")
    print(f"  ANTES  → {len(df_a):>6} filas | {df_a.isna().sum().sum():>5} nulos totales")
    print(f"  DESPUÉS → {len(df_d):>6} filas | {df_d.isna().sum().sum():>5} nulos totales")
    print(f"  Δ filas: {-delta_filas:+d}  |  Δ nulos: {-delta_nulos:+d}")

# ──────────────────────────────────────────────────────────────
# PASO 0 — CARGA Y DIAGNÓSTICO INICIAL
# ──────────────────────────────────────────────────────────────

sep("PASO 0: Carga del Dataset Crudo")

if not os.path.exists(RUTA_CRUDO):
    print(f"\n  ❌ ERROR: No se encontró {RUTA_CRUDO}")
    print("     Ejecuta primero: python 00_generar_datos.py")
    sys.exit(1)

df = pd.read_csv(RUTA_CRUDO)

print(f"\n  Archivo cargado: {RUTA_CRUDO}")
print(f"  Shape inicial  : {df.shape}  ({df.shape[0]} filas × {df.shape[1]} columnas)")
print(f"\n  Columnas:")
for col_name in df.columns:
    print(f"    {col_name:<20}: dtype={str(df[col_name].dtype):<10}  "
          f"nulos={df[col_name].isna().sum():>5}  "
          f"únicos={df[col_name].nunique():>6}")

print(f"\n  Vista previa (3 filas):")
print(df.head(3).to_string())

print(f"\n  Estadísticas descriptivas (numéricas):")
print(df[["temperatura", "humedad", "peso", "sonido"]].describe().round(2).to_string())

print(f"\n  Valores únicos en 'lluvia' (columna con formato mixto):")
print(f"    {df['lluvia'].unique()}")

df_original = df.copy()

# ──────────────────────────────────────────────────────────────
# PASO 1 — CORRECCIÓN DE TIPOS Y FORMATOS
# ──────────────────────────────────────────────────────────────

sep("PASO 1: Corrección de Tipos y Formatos")
df_antes = df.copy()

# 1a. fecha_registro → datetime
dtype_antes = df["fecha_registro"].dtype
df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
fechas_invalidas = df["fecha_registro"].isna().sum()
print(f"\n  [1a] fecha_registro")
print(f"       Tipo antes : {dtype_antes}")
print(f"       Tipo después: {df['fecha_registro'].dtype}")
print(f"       Fechas inválidas (→ NaT): {fechas_invalidas}")

# 1b. lluvia: normalizar formatos mixtos → INT 0/1
def normalizar_lluvia(val) -> int:
    """Mapea True/False/1/0/'si'/'no'/'true'/'false' a entero 0 o 1."""
    if pd.isna(val):
        return 0   # sin dato = sin lluvia (más probable)
    s = str(val).strip().lower()
    if s in ("true", "1", "si", "sí", "yes"):
        return 1
    if s in ("false", "0", "no"):
        return 0
    return 0

valores_antes = df["lluvia"].unique()
df["lluvia"] = df["lluvia"].apply(normalizar_lluvia).astype(np.int8)
print(f"\n  [1b] lluvia")
print(f"       Valores antes  : {valores_antes}")
print(f"       Valores después: {df['lluvia'].unique()}")
print(f"       Tipo después   : {df['lluvia'].dtype}")

# 1c. sensor_id → Int64 (nullable integer para conservar NaN)
df["sensor_id"] = pd.to_numeric(df["sensor_id"], errors="coerce").astype("Int64")
print(f"\n  [1c] sensor_id")
print(f"       Tipo después: {df['sensor_id'].dtype}  "
      f"(NaN conservados: {df['sensor_id'].isna().sum()})")

# 1d. Asegurar columnas numéricas correctas
for col_n in ["temperatura", "humedad", "peso", "sonido"]:
    df[col_n] = pd.to_numeric(df[col_n], errors="coerce")
print(f"\n  [1d] Columnas numéricas forzadas con pd.to_numeric(errors='coerce')")

antes_despues(df_antes, df, "Corrección de tipos y formatos")

# ──────────────────────────────────────────────────────────────
# PASO 2 — ELIMINACIÓN DE DUPLICADOS
# ──────────────────────────────────────────────────────────────

sep("PASO 2: Eliminación de Registros Duplicados")
df_antes = df.copy()

# 2a. Duplicados exactos (todas las columnas iguales)
dup_exactos = df.duplicated().sum()
df = df.drop_duplicates()
print(f"\n  [2a] Duplicados exactos eliminados  : {dup_exactos}")

# 2b. Duplicados por clave de negocio sensor_id + fecha_registro
df["fecha_registro"] = pd.to_datetime(df["fecha_registro"])
dup_clave = df.duplicated(subset=["sensor_id", "fecha_registro"]).sum()
df = df.drop_duplicates(subset=["sensor_id", "fecha_registro"])
print(f"  [2b] Dup. (sensor_id + timestamp)   : {dup_clave}")
print(f"       Criterio: mismo sensor no puede tener dos lecturas en el mismo instante.")

antes_despues(df_antes, df, "Eliminación de duplicados")

# ──────────────────────────────────────────────────────────────
# PASO 3 — ELIMINACIÓN DE REGISTROS HUÉRFANOS
# ──────────────────────────────────────────────────────────────

sep("PASO 3: Eliminación de Filas sin sensor_id (registros huérfanos)")
df_antes = df.copy()

sin_sensor = df["sensor_id"].isna().sum()
df = df.dropna(subset=["sensor_id"])
print(f"\n  Filas sin sensor_id eliminadas: {sin_sensor}")
print(f"  Justificación: sin identificador de sensor no se puede trazar")
print(f"  la lectura a ninguna colmena → descartable para análisis.")

antes_despues(df_antes, df, "Eliminación registros huérfanos")

# ──────────────────────────────────────────────────────────────
# PASO 4 — DETECCIÓN Y TRATAMIENTO DE OUTLIERS
# ──────────────────────────────────────────────────────────────

sep("PASO 4: Detección y Tratamiento de Outliers")
df_antes = df.copy()

def diagnostico_iqr(serie: pd.Series, nombre: str):
    """Calcula y muestra límites IQR y cuenta outliers."""
    Q1  = serie.quantile(0.25)
    Q3  = serie.quantile(0.75)
    IQR = Q3 - Q1
    lim_inf = Q1 - 1.5 * IQR
    lim_sup = Q3 + 1.5 * IQR
    n_out = serie[(serie < lim_inf) | (serie > lim_sup)].count()
    print(f"\n  [{nombre}]")
    print(f"    Q1={Q1:.2f}  Q3={Q3:.2f}  IQR={IQR:.2f}")
    print(f"    Límites IQR: [{lim_inf:.2f}, {lim_sup:.2f}]")
    print(f"    Outliers estadísticos: {n_out} ({n_out/len(serie)*100:.2f}%)")
    return lim_inf, lim_sup

# Temperatura — regla de negocio basada en biología de Apis mellifera
_, _ = diagnostico_iqr(df["temperatura"].dropna(), "temperatura (diagnóstico IQR)")
TEMP_MIN, TEMP_MAX = 0.0, 45.0
mask_temp_out = df["temperatura"].notna() & ((df["temperatura"] < TEMP_MIN) | (df["temperatura"] > TEMP_MAX))
n_temp_out = mask_temp_out.sum()
df.loc[mask_temp_out, "temperatura"] = np.nan
print(f"    → Regla de negocio: temperatura fuera de [{TEMP_MIN}, {TEMP_MAX}]°C → NaN")
print(f"    → Outliers invalidados: {n_temp_out}")

# Humedad — físicamente imposible fuera de [0, 100]
_, _ = diagnostico_iqr(df["humedad"].dropna(), "humedad (diagnóstico IQR)")
mask_hum_out = df["humedad"].notna() & ((df["humedad"] < 0) | (df["humedad"] > 100))
n_hum_out = mask_hum_out.sum()
df.loc[mask_hum_out, "humedad"] = np.nan
print(f"    → Regla de negocio: humedad fuera de [0, 100]% → NaN")
print(f"    → Outliers invalidados: {n_hum_out}")

# Sonido — fuera del rango del sensor ESP32
_, _ = diagnostico_iqr(df["sonido"].dropna(), "sonido (diagnóstico IQR)")
mask_snd_out = df["sonido"].notna() & ((df["sonido"] < 15) | (df["sonido"] > 100))
n_snd_out = mask_snd_out.sum()
df.loc[mask_snd_out, "sonido"] = np.nan
print(f"    → Regla de negocio: sonido fuera de [15, 100] dB → NaN")
print(f"    → Outliers invalidados: {n_snd_out}")

print(f"\n  Total de outliers invalidados: {n_temp_out + n_hum_out + n_snd_out}")
antes_despues(df_antes, df, "Tratamiento de outliers")

# ──────────────────────────────────────────────────────────────
# PASO 5 — IMPUTACIÓN DE VALORES NULOS
# ──────────────────────────────────────────────────────────────

sep("PASO 5: Imputación de Valores Nulos (Series Temporales)")
df_antes = df.copy()

print(f"\n  Nulos ANTES de imputación:")
nulos_antes = df[["temperatura", "humedad", "sonido", "peso"]].isna().sum()
for col_n, cnt in nulos_antes.items():
    print(f"    {col_n:<15}: {cnt:>5} ({cnt/len(df)*100:.2f}%)")

# Ordenar cronológicamente por sensor para que ffill tenga sentido
df = df.sort_values(["sensor_id", "fecha_registro"]).reset_index(drop=True)

# Forward fill + backward fill por grupo de sensor
# Apropiado para series temporales: el valor más reciente es la mejor estimación
for col_n in ["temperatura", "humedad", "sonido"]:
    df[col_n] = (
        df.groupby("sensor_id")[col_n]
        .transform(lambda x: x.ffill().bfill())
    )
    print(f"\n  [ffill+bfill] {col_n} → nulos restantes: {df[col_n].isna().sum()}")

# Peso: solo Multisensor tiene peso; si el sensor no tiene peso, NaN es correcto
# Para los que tienen peso, interpolación lineal (crecimiento gradual esperado)
df["peso"] = (
    df.groupby("sensor_id")["peso"]
    .transform(
        lambda x: (
            x.interpolate(method="linear").ffill().bfill()
            if x.notna().any() else x
        )
    )
)
print(f"\n  [interpolación lineal] peso → nulos restantes: {df['peso'].isna().sum()}")
print(f"    (Nulos en peso = colmenas sin sensor de peso; esto es CORRECTO)")

print(f"\n  Nulos DESPUÉS de imputación:")
nulos_despues = df[["temperatura", "humedad", "sonido", "peso"]].isna().sum()
for col_n, cnt in nulos_despues.items():
    print(f"    {col_n:<15}: {cnt:>5} ({cnt/len(df)*100:.2f}%)")

antes_despues(df_antes, df, "Imputación de nulos")

# ──────────────────────────────────────────────────────────────
# PASO 6 — NORMALIZACIÓN SINTÁCTICA Y ENRIQUECIMIENTO TEMPORAL
# ──────────────────────────────────────────────────────────────

sep("PASO 6: Normalización Sintáctica y Enriquecimiento de Features")
df_antes = df.copy()

# Extraer componentes temporales para análisis posterior
df["año"]          = df["fecha_registro"].dt.year
df["mes"]          = df["fecha_registro"].dt.month
df["semana"]       = df["fecha_registro"].dt.isocalendar().week.astype(int)
df["dia_semana"]   = df["fecha_registro"].dt.dayofweek       # 0=lunes, 6=domingo
df["hora"]         = df["fecha_registro"].dt.hour
df["es_fin_semana"] = (df["dia_semana"] >= 5).astype(np.int8)
df["es_noche"]     = (~df["hora"].between(7, 19)).astype(np.int8)

def clasificar_periodo(hora: int) -> str:
    if hora < 6:   return "madrugada"
    if hora < 12:  return "manana"
    if hora < 18:  return "tarde"
    return "noche"

df["periodo_dia"] = df["hora"].apply(clasificar_periodo)

# Asegurar tipos correctos en columnas clave
df["sensor_id"]  = df["sensor_id"].astype(int)
df["colmena_id"] = df["colmena_id"].astype(int)

print(f"\n  Columnas derivadas añadidas: año, mes, semana, dia_semana, hora,")
print(f"  es_fin_semana, es_noche, periodo_dia")
print(f"\n  Tipos finales:")
for col_n in df.columns:
    print(f"    {col_n:<22}: {str(df[col_n].dtype)}")

# ──────────────────────────────────────────────────────────────
# PASO 7 — VALIDACIÓN FINAL
# ──────────────────────────────────────────────────────────────

sep("PASO 7: Validación Final del Dataset Limpio")

print(f"\n  Shape final: {df.shape}")
print(f"\n  Estadísticas descriptivas post-limpieza:")
print(df[["temperatura", "humedad", "peso", "sonido"]].describe().round(3).to_string())

print(f"\n  Distribución por tipo de sensor:")
print(df["tipo_sensor"].value_counts().to_string())

print(f"\n  Distribución por colmena:")
print(df["colmena_nombre"].value_counts().to_string())

print(f"\n  Rango de fechas:")
print(f"    Mínima: {df['fecha_registro'].min()}")
print(f"    Máxima: {df['fecha_registro'].max()}")

print(f"\n  Nulos restantes por columna:")
nulos_final = df.isna().sum()
cols_con_nulos = nulos_final[nulos_final > 0]
if len(cols_con_nulos) == 0:
    print("    Ninguno (excepto peso en sensores sin báscula — esperado ✓)")
else:
    print(cols_con_nulos.to_string())

# Verificar rangos biológicos
assert df["temperatura"].dropna().between(0, 45).all(),   "⚠️ Temperatura fuera de rango"
assert df["humedad"].dropna().between(0, 100).all(),       "⚠️ Humedad fuera de rango"
assert df["lluvia"].isin([0, 1]).all(),                    "⚠️ lluvia no binario"
print(f"\n  ✅ Validaciones de rango superadas")

# ──────────────────────────────────────────────────────────────
# GUARDAR
# ──────────────────────────────────────────────────────────────

sep("GUARDADO DEL DATASET LIMPIO")
df.to_csv(RUTA_LIMPIO, index=False, encoding="utf-8")
print(f"\n  ✅ Dataset limpio guardado: {RUTA_LIMPIO}")
print(f"     Shape          : {df.shape}")
print(f"     Columnas totales: {len(df.columns)}")
print(f"     Columnas       : {list(df.columns)}")

# Resumen del pipeline
sep("RESUMEN DEL PIPELINE DE LIMPIEZA")
reduccion = len(df_original) - len(df)
print(f"""
  Dataset original   : {len(df_original):>6} filas
  Dataset final      : {len(df):>6} filas
  Registros removidos: {reduccion:>6} ({reduccion/len(df_original)*100:.2f}%)

  Pasos aplicados:
  1. Corrección de tipos   → fechas, lluvia str→int, sensor_id nullable
  2. Duplicados exactos    → eliminados
  3. Dup. sensor+timestamp → eliminados
  4. Huérfanos sin sensor  → eliminados
  5. Outliers temperatura  → [{TEMP_MIN}, {TEMP_MAX}°C] — inválidos → NaN → imputados
  6. Outliers humedad      → [0, 100%]  — inválidos → NaN → imputados
  7. Outliers sonido       → [15, 100 dB] — inválidos → NaN → imputados
  8. Imputación nulos      → ffill+bfill por grupo de sensor (series temporales)
  9. Peso                  → interpolación lineal por sensor (crecimiento gradual)
  10. Enriquecimiento      → 8 features temporales derivadas

  Log de ejecución guardado en: {RUTA_LOG}
""")

# Cerrar log
sys.stdout = sys.__stdout__
log_file.close()
print(f"Pipeline completo. Revisa '{RUTA_LIMPIO}' y '{RUTA_LOG}'.")
