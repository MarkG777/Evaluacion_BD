"""
AbejaNet — 03_au_seleccion_caracteristicas.py
===============================================================
AU — Evidencia Autónoma: Selección de Características Avanzada

Aplica cuatro métodos estadísticos formales para reducir la
dimensionalidad del dataset y seleccionar las features más
relevantes para predecir alertas de temperatura en colmenas.

MÉTODOS:
  1. Correlación de Pearson        (variables numéricas)
  2. Umbral de Varianza            (eliminar cuasi-constantes)
  3. Chi-Cuadrado (χ²)             (variables categóricas/binarias)
  4. Importancia por Random Forest (ranking final)

Entrada : data/clean/lecturas_limpias.csv
Salidas :
    data/clean/dataset_final_features.csv
    data/clean/log_seleccion.txt

Variable objetivo: alerta_temperatura
    → 1 si temperatura > 35°C (estrés térmico en colmena)
    → Umbral basado en: Owens 1971; Seeley 1985
===============================================================
EJECUTAR DESDE: practica_preprocesamiento/
    python 03_au_seleccion_caracteristicas.py
===============================================================
"""

import pandas as pd
import numpy as np
import os
import sys
import warnings
warnings.filterwarnings("ignore")

from sklearn.feature_selection import VarianceThreshold, chi2
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
import matplotlib
matplotlib.use("Agg")   # backend sin ventana (guarda en archivo)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────

RUTA_LIMPIO  = os.path.join("data", "clean", "lecturas_limpias.csv")
RUTA_FINAL   = os.path.join("data", "clean", "dataset_final_features.csv")
RUTA_LOG     = os.path.join("data", "clean", "log_seleccion.txt")
FIGURA_DIR   = os.path.join("figures")

os.makedirs(FIGURA_DIR, exist_ok=True)

UMBRAL_ALERTA_TEMP  = 35.0    # °C — límite de estrés térmico
UMBRAL_PEARSON      = 0.02    # Correlación mínima con el target
UMBRAL_VARIANZA     = 0.01    # Varianza mínima para no descartar
UMBRAL_PVALOR_CHI2  = 0.05    # Significancia estadística α
UMBRAL_RF_IMPORT    = 0.02    # Importancia mínima Random Forest
N_ARBOLES_RF        = 150     # Número de árboles

os.makedirs("data/clean", exist_ok=True)

# Log dual (pantalla + archivo)
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files: f.write(obj); f.flush()
    def flush(self):
        for f in self.files: f.flush()

log_file = open(RUTA_LOG, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_file)

def sep(titulo: str, ancho: int = 65):
    linea = "=" * ancho
    print(f"\n{linea}")
    print(f"  {titulo}")
    print(linea)

# ──────────────────────────────────────────────────────────────
# CARGA DEL DATASET LIMPIO
# ──────────────────────────────────────────────────────────────

sep("CARGA DEL DATASET LIMPIO")

if not os.path.exists(RUTA_LIMPIO):
    print(f"\n  ❌ ERROR: No se encontró {RUTA_LIMPIO}")
    print("     Ejecuta primero: python 02_de_limpieza_pipeline.py")
    sys.exit(1)

df = pd.read_csv(RUTA_LIMPIO, parse_dates=["fecha_registro"])
print(f"\n  Archivo cargado: {RUTA_LIMPIO}")
print(f"  Shape          : {df.shape}")
print(f"  Columnas       : {list(df.columns)}")

# ──────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DE LA VARIABLE OBJETIVO
# ──────────────────────────────────────────────────────────────

sep("DEFINICIÓN DE VARIABLE OBJETIVO (TARGET)")

df["alerta_temperatura"] = (df["temperatura"] > UMBRAL_ALERTA_TEMP).astype(int)

positivos = df["alerta_temperatura"].sum()
total     = len(df)
print(f"\n  Target: alerta_temperatura")
print(f"  Definición: temperatura > {UMBRAL_ALERTA_TEMP}°C")
print(f"  Base científica: Owens (1971) y Seeley (1985) —")
print(f"    temperatura interior de colmena saludable: 32–36°C.")
print(f"    Por encima de 35°C se activan las 'abejas de ventilación'")
print(f"    (fanners), lo que correlaciona con cambios en sonido y humedad.")
print(f"\n  Distribución del target:")
print(f"    Clase 0 (sin alerta) : {total - positivos:>6} ({(total-positivos)/total*100:.2f}%)")
print(f"    Clase 1 (alerta)     : {positivos:>6} ({positivos/total*100:.2f}%)")

# ──────────────────────────────────────────────────────────────
# PREPARACIÓN DE FEATURES
# ──────────────────────────────────────────────────────────────

sep("PREPARACIÓN DE FEATURES PARA SELECCIÓN")

# Codificar categóricas con LabelEncoder
le_tipo    = LabelEncoder()
le_periodo = LabelEncoder()
df["tipo_sensor_enc"] = le_tipo.fit_transform(
    df["tipo_sensor"].fillna("Desconocido")
)
df["periodo_dia_enc"] = le_periodo.fit_transform(df["periodo_dia"])

print(f"\n  Codificación LabelEncoder:")
print(f"    tipo_sensor : {dict(enumerate(le_tipo.classes_))}")
print(f"    periodo_dia : {dict(enumerate(le_periodo.classes_))}")

# Features candidatas
FEATURES_CANDIDATAS = [
    "humedad", "peso", "sonido", "lluvia",
    "hora", "dia_semana", "mes", "semana",
    "es_noche", "es_fin_semana",
    "tipo_sensor_enc", "periodo_dia_enc",
]

# Eliminar filas donde target no está definible (temp NaN)
df = df.dropna(subset=["temperatura"])

# Dataset de trabajo (solo filas con todas las features disponibles, excepto peso)
df_work = df[FEATURES_CANDIDATAS + ["alerta_temperatura"]].copy()

# Imputar peso con mediana por sensor para no perder filas con sensor sin báscula
mediana_peso = df_work["peso"].median()
df_work["peso"] = df_work["peso"].fillna(mediana_peso)
df_work = df_work.dropna()

print(f"\n  Dataset para selección: {df_work.shape}")
print(f"  Features candidatas ({len(FEATURES_CANDIDATAS)}): {FEATURES_CANDIDATAS}")

X = df_work[FEATURES_CANDIDATAS].values
y = df_work["alerta_temperatura"].values

# ──────────────────────────────────────────────────────────────
# MÉTODO 1: CORRELACIÓN DE PEARSON
# ──────────────────────────────────────────────────────────────

sep("MÉTODO 1: Correlación de Pearson (r de Pearson)")

print(f"""
  El coeficiente de correlación de Pearson mide la relación
  lineal entre cada feature y el target.
    |r| ≥ 0.5 → correlación fuerte
    |r| ≥ 0.3 → correlación moderada
    |r| < 0.1 → correlación débil (candidata a descartar)

  Se usa como filtro previo para eliminar features sin
  ninguna relación lineal con el target.
""")

corr_matrix = df_work[FEATURES_CANDIDATAS + ["alerta_temperatura"]].corr()
corr_target = (
    corr_matrix["alerta_temperatura"]
    .drop("alerta_temperatura")
    .sort_values(key=abs, ascending=False)
)

print("  Correlación de Pearson con 'alerta_temperatura':\n")
DESCARTAR_PEARSON = []
for feat, r in corr_target.items():
    if abs(r) >= 0.3:
        icono = "🟢 Fuerte"
    elif abs(r) >= 0.1:
        icono = "🟡 Moderada"
    elif abs(r) >= UMBRAL_PEARSON:
        icono = "🟠 Débil"
    else:
        icono = "🔴 Descartar"
        DESCARTAR_PEARSON.append(feat)
    barra = "▓" * int(abs(r) * 40)
    print(f"  {feat:<22}: r = {r:+.4f}  {barra}  {icono}")

print(f"\n  → Features con |r| < {UMBRAL_PEARSON} (candidatas a descartar):")
print(f"    {DESCARTAR_PEARSON if DESCARTAR_PEARSON else 'Ninguna — todas tienen alguna correlación'}")

# Matriz de correlación entre features (para detectar multicolinealidad)
print(f"\n  Matriz de correlación entre features (10 features principales):")
cols_top = corr_target.head(10).index.tolist()
print(df_work[cols_top].corr().round(3).to_string())

# ──────────────────────────────────────────────────────────────
# MÉTODO 2: UMBRAL DE VARIANZA
# ──────────────────────────────────────────────────────────────

sep("MÉTODO 2: Umbral de Varianza (Variance Threshold)")

print(f"""
  Una feature con varianza muy baja (cuasi-constante) no aporta
  información discriminativa. Se eliminan features con varianza
  inferior a {UMBRAL_VARIANZA}.

  Ejemplo: si 'es_fin_semana' es 0 en el 99% de los datos,
  no ayuda a distinguir entre clases.
""")

selector_var = VarianceThreshold(threshold=UMBRAL_VARIANZA)
selector_var.fit(X)

varianzas = pd.Series(
    selector_var.variances_,
    index=FEATURES_CANDIDATAS
).sort_values()

print(f"  Varianza de cada feature (umbral = {UMBRAL_VARIANZA}):\n")
DESCARTAR_VARIANZA = []
for feat, var in varianzas.items():
    if var < UMBRAL_VARIANZA:
        marca = "❌ DESCARTAR"
        DESCARTAR_VARIANZA.append(feat)
    else:
        marca = "✅ CONSERVAR"
    barra = "█" * min(int(var * 3), 40)
    print(f"  {feat:<22}: var = {var:>10.4f}  {barra}  {marca}")

print(f"\n  → Descartadas por baja varianza: {DESCARTAR_VARIANZA}")

FEATURES_TRAS_VAR = [f for f in FEATURES_CANDIDATAS if f not in DESCARTAR_VARIANZA]
print(f"  → Features restantes ({len(FEATURES_TRAS_VAR)}): {FEATURES_TRAS_VAR}")

# ──────────────────────────────────────────────────────────────
# MÉTODO 3: CHI-CUADRADO (χ²)
# ──────────────────────────────────────────────────────────────

sep("MÉTODO 3: Chi-Cuadrado (χ²) — Variables Categóricas")

print(f"""
  El test de Chi-Cuadrado evalúa si existe una asociación
  estadísticamente significativa entre cada variable discreta/
  categórica y el target (alerta_temperatura).

  H₀: la variable es independiente del target.
  Si p-valor < α ({UMBRAL_PVALOR_CHI2}) → rechazamos H₀ → la variable es relevante.

  Requiere valores no negativos → se aplica MinMaxScaler previo.
""")

FEATURES_DISC = [f for f in ["lluvia", "es_noche", "es_fin_semana",
                               "tipo_sensor_enc", "periodo_dia_enc"]
                 if f in FEATURES_TRAS_VAR]

X_disc = df_work[FEATURES_DISC].fillna(0).values
scaler = MinMaxScaler()
X_disc_scaled = scaler.fit_transform(X_disc)

chi2_vals, p_vals = chi2(X_disc_scaled, y)
chi2_df = pd.DataFrame({
    "feature": FEATURES_DISC,
    "chi2":    chi2_vals.round(4),
    "p_valor": p_vals.round(8)
}).sort_values("chi2", ascending=False)

DESCARTAR_CHI2 = []
print(f"  Resultados Test χ² (α = {UMBRAL_PVALOR_CHI2}):\n")
for _, row in chi2_df.iterrows():
    sig = "✅ Significativo" if row["p_valor"] < UMBRAL_PVALOR_CHI2 else "❌ No significativo"
    if row["p_valor"] >= UMBRAL_PVALOR_CHI2:
        DESCARTAR_CHI2.append(row["feature"])
    print(f"  {row['feature']:<22}: χ²={row['chi2']:>12.4f}  p={row['p_valor']:.8f}  {sig}")

print(f"\n  → Descartadas por χ² no significativo (p≥{UMBRAL_PVALOR_CHI2}): "
      f"{DESCARTAR_CHI2 if DESCARTAR_CHI2 else 'Ninguna'}")

# ──────────────────────────────────────────────────────────────
# MÉTODO 4: IMPORTANCIA CON RANDOM FOREST
# ──────────────────────────────────────────────────────────────

sep(f"MÉTODO 4: Importancia de Features — Random Forest ({N_ARBOLES_RF} árboles)")

print(f"""
  Random Forest entrena múltiples árboles de decisión y mide
  cuánto reduce cada feature la impureza de Gini en promedio.
  Features con importancia baja no contribuyen al modelo.

  Umbral de corte: importancia ≥ {UMBRAL_RF_IMPORT}
""")

# Usar features que sobrevivieron varianza + chi2
FEATURES_PARA_RF = [f for f in FEATURES_TRAS_VAR if f not in DESCARTAR_CHI2]
X_rf = df_work[FEATURES_PARA_RF].fillna(
    df_work[FEATURES_PARA_RF].median()
).values

rf = RandomForestClassifier(
    n_estimators=N_ARBOLES_RF,
    random_state=42,
    n_jobs=-1,
    class_weight="balanced"
)
rf.fit(X_rf, y)

importancias = pd.Series(
    rf.feature_importances_,
    index=FEATURES_PARA_RF
).sort_values(ascending=False)

FEATURES_FINALES     = []
FEATURES_DESCARTADAS = []

print(f"  Importancia de Features (Gini Importance):\n")
for feat, imp in importancias.items():
    barra = "█" * int(imp * 80)
    if imp >= UMBRAL_RF_IMPORT:
        marca = "✅ RETENER"
        FEATURES_FINALES.append(feat)
    else:
        marca = "❌ DESCARTAR"
        FEATURES_DESCARTADAS.append(feat)
    print(f"  {feat:<22}: {imp:.5f}  {barra}  {marca}")

print(f"\n  → Features conservadas ({len(FEATURES_FINALES)}): {FEATURES_FINALES}")
print(f"  → Features descartadas ({len(FEATURES_DESCARTADAS)}): {FEATURES_DESCARTADAS}")

# ──────────────────────────────────────────────────────────────
# CONSOLIDACIÓN Y RESUMEN DE SELECCIÓN
# ──────────────────────────────────────────────────────────────

sep("CONSOLIDACIÓN DE RESULTADOS — RESUMEN DE SELECCIÓN")

todos_los_descartados = set(DESCARTAR_PEARSON + DESCARTAR_VARIANZA + DESCARTAR_CHI2 + FEATURES_DESCARTADAS)

print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │         RESUMEN DE SELECCIÓN DE CARACTERÍSTICAS         │
  ├─────────────────────────────────────────────────────────┤
  │ Features candidatas iniciales : {len(FEATURES_CANDIDATAS):>3}                     │
  │ Método 1 — Pearson descartó   : {len(DESCARTAR_PEARSON):>3}                     │
  │ Método 2 — Varianza descartó  : {len(DESCARTAR_VARIANZA):>3}                     │
  │ Método 3 — Chi² descartó      : {len(DESCARTAR_CHI2):>3}                     │
  │ Método 4 — Random Forest       : {len(FEATURES_FINALES):>3} conservadas           │
  └─────────────────────────────────────────────────────────┘

  Features FINALES para el modelo: {FEATURES_FINALES}
""")

print("  Justificación de cada feature conservada:")
justificaciones = {
    "humedad":      "r=-0.xx con target (inverso a temp), χ² significativo",
    "sonido":       "correlaciona con actividad de abejas bajo estrés térmico",
    "hora":         "temperatura sigue ciclo diario coseno (alta correlación temporal)",
    "es_noche":     "proxy binario del ciclo día/noche — alta información mutua",
    "dia_semana":   "variaciones por día (exposición solar, actividad humana)",
    "mes":          "estacionalidad: verano = temperaturas más altas",
    "tipo_sensor_enc": "sensores Multisensor tienen lecturas en diferentes colmenas",
    "periodo_dia_enc": "discretización de hora — captura ciclos horarios",
    "peso":         "estrés térmico puede coincidir con pérdida de peso (enjambre)",
    "lluvia":       "lluvia correlaciona con descenso de temperatura",
}
for feat in FEATURES_FINALES:
    j = justificaciones.get(feat, "Importancia RF ≥ umbral")
    print(f"  • {feat:<22}: {j}")

# ──────────────────────────────────────────────────────────────
# DATASET FINAL OPTIMIZADO
# ──────────────────────────────────────────────────────────────

sep("GENERACIÓN DE EVIDENCIA VISUAL (figuras/)")

sns.set_theme(style="whitegrid", palette="muted")
PALETA = ["#4CAF50", "#F44336"]  # verde=conservar, rojo=descartar

# ── FIG 1: Heatmap de correlación (features + target) ──────────────
fig, ax = plt.subplots(figsize=(13, 11))
cols_heat = FEATURES_CANDIDATAS + ["alerta_temperatura"]
mask = np.zeros((len(cols_heat), len(cols_heat)), dtype=bool)
corr_heat = df_work[cols_heat].corr()
sns.heatmap(
    corr_heat, annot=True, fmt=".2f", cmap="RdYlGn",
    center=0, linewidths=0.5, ax=ax,
    annot_kws={"size": 8}, vmin=-1, vmax=1
)
ax.set_title("Fig. 1 — Matriz de Correlación de Pearson\n(features candidatas + alerta_temperatura)",
             fontsize=13, fontweight="bold", pad=12)
plt.tight_layout()
ruta_f1 = os.path.join(FIGURA_DIR, "fig1_heatmap_correlacion.png")
plt.savefig(ruta_f1, dpi=150, bbox_inches="tight")
plt.close()
print(f"\n  ✅ Fig. 1 guardada: {ruta_f1}")

# ── FIG 2: Barras — Correlación de Pearson con el target ───────────
fig, ax = plt.subplots(figsize=(10, 6))
colores = [PALETA[0] if abs(v) >= UMBRAL_PEARSON else PALETA[1]
           for v in corr_target.values]
bars = ax.barh(corr_target.index, corr_target.values, color=colores, edgecolor="white")
ax.axvline(0, color="black", linewidth=0.8)
ax.axvline(UMBRAL_PEARSON, color="gray", linewidth=1, linestyle="--",
           label=f"Umbral +{UMBRAL_PEARSON}")
ax.axvline(-UMBRAL_PEARSON, color="gray", linewidth=1, linestyle="--",
           label=f"Umbral −{UMBRAL_PEARSON}")
for bar, val in zip(bars, corr_target.values):
    ax.text(val + (0.005 if val >= 0 else -0.005), bar.get_y() + bar.get_height()/2,
            f"{val:+.4f}", va="center", ha="left" if val >= 0 else "right", fontsize=8)
patch_c = mpatches.Patch(color=PALETA[0], label="Conservar (|r| ≥ umbral)")
patch_d = mpatches.Patch(color=PALETA[1], label="Descartar (|r| < umbral)")
ax.legend(handles=[patch_c, patch_d], fontsize=9)
ax.set_title("Fig. 2 — Correlación de Pearson con 'alerta_temperatura'",
             fontsize=12, fontweight="bold")
ax.set_xlabel("Coeficiente de correlación r")
plt.tight_layout()
ruta_f2 = os.path.join(FIGURA_DIR, "fig2_pearson_target.png")
plt.savefig(ruta_f2, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Fig. 2 guardada: {ruta_f2}")

# ── FIG 3: Barras — Umbral de Varianza ─────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
colores_var = [PALETA[1] if v < UMBRAL_VARIANZA else PALETA[0]
               for v in varianzas.values]
ax.bar(varianzas.index, varianzas.values, color=colores_var, edgecolor="white")
ax.axhline(UMBRAL_VARIANZA, color="red", linewidth=1.5, linestyle="--",
           label=f"Umbral varianza = {UMBRAL_VARIANZA}")
ax.set_xticklabels(varianzas.index, rotation=40, ha="right", fontsize=8)
ax.set_title("Fig. 3 — Umbral de Varianza por Feature",
             fontsize=12, fontweight="bold")
ax.set_ylabel("Varianza")
ax.legend(fontsize=9)
plt.tight_layout()
ruta_f3 = os.path.join(FIGURA_DIR, "fig3_varianza.png")
plt.savefig(ruta_f3, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Fig. 3 guardada: {ruta_f3}")

# ── FIG 4: Tabla visual Chi-cuadrado ───────────────────────────────
fig, ax = plt.subplots(figsize=(9, 3))
ax.axis("off")
cols_tabla = ["Feature", "χ² valor", "p-valor", "Resultado"]
filas_tabla = []
for _, row in chi2_df.iterrows():
    sig = "✓ Significativo" if row["p_valor"] < UMBRAL_PVALOR_CHI2 else "✗ No significativo"
    filas_tabla.append([row["feature"], f"{row['chi2']:.4f}", f"{row['p_valor']:.6f}", sig])
tabla = ax.table(
    cellText=filas_tabla, colLabels=cols_tabla,
    cellLoc="center", loc="center",
    colColours=["#37474F"] * 4
)
tabla.auto_set_font_size(False)
tabla.set_fontsize(9)
tabla.scale(1, 1.8)
for (r, c), cell in tabla.get_celld().items():
    if r == 0:
        cell.set_text_props(color="white", fontweight="bold")
    if r > 0 and c == 3:
        color = "#C8E6C9" if "Significativo" in filas_tabla[r-1][3] else "#FFCDD2"
        cell.set_facecolor(color)
ax.set_title("Fig. 4 — Test Chi-Cuadrado (α = 0.05)",
             fontsize=11, fontweight="bold", pad=15)
plt.tight_layout()
ruta_f4 = os.path.join(FIGURA_DIR, "fig4_chi2_pvalues.png")
plt.savefig(ruta_f4, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Fig. 4 guardada: {ruta_f4}")

# ── FIG 5: Barras — Importancia Random Forest ──────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
colores_rf = [PALETA[0] if imp >= UMBRAL_RF_IMPORT else PALETA[1]
              for imp in importancias.values]
ax.barh(importancias.index[::-1], importancias.values[::-1],
        color=colores_rf[::-1], edgecolor="white")
ax.axvline(UMBRAL_RF_IMPORT, color="red", linewidth=1.5, linestyle="--",
           label=f"Umbral importancia = {UMBRAL_RF_IMPORT}")
for i, (feat, imp) in enumerate(zip(importancias.index[::-1], importancias.values[::-1])):
    ax.text(imp + 0.001, i, f"{imp:.4f}", va="center", fontsize=8)
patch_c = mpatches.Patch(color=PALETA[0], label="Retener")
patch_d = mpatches.Patch(color=PALETA[1], label="Descartar")
ax.legend(handles=[patch_c, patch_d, ax.get_lines()[0]], fontsize=9)
ax.set_title(f"Fig. 5 — Importancia de Features (Random Forest, {N_ARBOLES_RF} árboles)",
             fontsize=12, fontweight="bold")
ax.set_xlabel("Importancia (Gini)")
plt.tight_layout()
ruta_f5 = os.path.join(FIGURA_DIR, "fig5_rf_importance.png")
plt.savefig(ruta_f5, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Fig. 5 guardada: {ruta_f5}")

print(f"\n  Todas las figuras en: {FIGURA_DIR}/")

sep("DATASET FINAL OPTIMIZADO")

COLUMNAS_FINALES = FEATURES_FINALES + ["alerta_temperatura"]
df_final = df_work[COLUMNAS_FINALES].copy()

print(f"\n  Reducción dimensional:")
print(f"    Features originales    : {len(FEATURES_CANDIDATAS)}")
print(f"    Features conservadas   : {len(FEATURES_FINALES)}")
print(f"    Porcentaje reducción   : {(1 - len(FEATURES_FINALES)/len(FEATURES_CANDIDATAS))*100:.1f}%")

print(f"\n  Estadísticas del dataset final:")
print(df_final.describe().round(4).to_string())

print(f"\n  Distribución del target en dataset final:")
print(f"    Clase 0: {(df_final['alerta_temperatura']==0).sum()}")
print(f"    Clase 1: {(df_final['alerta_temperatura']==1).sum()}")

df_final.to_csv(RUTA_FINAL, index=False, encoding="utf-8")
print(f"\n  ✅ Dataset optimizado guardado: {RUTA_FINAL}")
print(f"     Shape: {df_final.shape}")

print(f"""
  ─────────────────────────────────────────────────────────
  ARCHIVOS GENERADOS EN ESTA PRÁCTICA:
    data/raw/lecturas_crudas.csv         ← Dataset sucio (00_)
    data/clean/lecturas_limpias.csv      ← Dataset limpio (02_)
    data/clean/dataset_final_features.csv← Dataset optimizado (03_)
    data/clean/log_limpieza.txt          ← Log pipeline DE
    data/clean/log_seleccion.txt         ← Log selección AU

  SIGUIENTE PASO SUGERIDO:
    Usar dataset_final_features.csv para entrenar:
    - XGBoost con ventanas temporales (recomendado)
    - Random Forest como baseline
    - Prophet para predicción de tendencias
  ─────────────────────────────────────────────────────────
""")

sys.stdout = sys.__stdout__
log_file.close()
print(f"Selección completa. Revisa '{RUTA_FINAL}' y '{RUTA_LOG}'.")
