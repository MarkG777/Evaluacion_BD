# AbejaNet — Práctica: Preprocesamiento y Almacenamiento de Datos
## Materia: Extracción de Conocimiento en Bases de Datos
### Contexto completo para retomar en cualquier sesión futura

---

## 1. QUÉ PIDE LA PRÁCTICA

### SA — Saber (Documento de Arquitectura y Repositorio)
Construir un documento técnico con:
- **Esquema de Data Warehouse en Estrella (Star Schema):** diagrama conceptual con tabla de hechos y dimensiones.
- **Inventario de fuentes y tipos de datos:** clasificar cada variable como nominal, ordinal, continua o discreta.
- **Técnicas de limpieza justificadas:** qué algoritmos y reglas se aplicaron (nulos, duplicados, outliers, formatos).
- **Parámetros de configuración del DW:** motor usado (PostgreSQL local), índices, estrategia de partición.
- **Entregable técnico (Repositorio):** link a GitHub + dataset preprocesado + scripts.

### DE — Desempeño (Reporte de Limpieza Paso a Paso)
- Evidencia visual del "antes y después" de cada transformación.
- Código aplicando técnicas de limpieza: nulos, duplicados, outliers, formatos, normalización sintáctica.
- Capturas de pantalla de cada paso (o logs impresos).
- Archivos generados: `lecturas_crudas.csv`, `lecturas_limpias.csv`.

### AU — Autónomo (Selección de Características Avanzada)
- Aplicar **al menos un método estadístico formal** justificado:
  - **Correlación de Pearson** (variables numéricas)
  - **Chi-Cuadrado (χ²)** (variables categóricas)
  - **Umbral de Varianza**
  - **Importancia Random Forest**
- Evidencia visual: matriz de correlación, tabla de p-values, ranking de importancia.
- Entregable: `dataset_final_features.csv` con dimensiones reducidas.

### Rúbrica resumida
| Nivel     | SA                                  | DE                                   | AU                                      |
|-----------|-------------------------------------|--------------------------------------|-----------------------------------------|
| Excelente | Esquema DW completo + config rigorosa + repo funcional | Capturas claras + archivos sin errores | Métodos estadísticos avanzados + dataset optimizado final |
| Satisf.   | Esquema + fuentes pero config superficial | Limpieza realizada pero sin capturas intermedias | Selección sin justificación estadística fuerte |
| Insufic.  | Sin esquema DW o sin repo           | Sin capturas o archivos inconsistentes | Sin modelos estadísticos aplicados      |

---

## 2. CONTEXTO DEL PROYECTO: AbejaNet

**Descripción:** Plataforma IoT + App Móvil para monitoreo de colmenas de abejas.

**Stack:**
- **App Móvil:** React Native / Expo SDK 51, TypeScript, expo-router
- **Backend:** Node.js + Express (ESM), PostgreSQL via `pg` pool, JWT auth
- **IoT:** ESP32 → POST `/api/sensor-data` cada 10 min con header `X-API-Key`
- **Deploy:** Render (backend), EAS Build (APK Android)

**Apiarios y Colmenas en el sistema:**
| Apiario | Colmena | Sensor MAC | Tipo Sensor |
|---------|---------|-----------|-------------|
| Apiario Principal | Colmena Alfa Ppal | `AA:BB:CC:11:22:33` | Temperatura/Humedad |
| Apiario Principal | Colmena Gamma Ppal | `AA:BB:CC:11:22:44` | Multisensor (con peso) |
| Apiario Laboratorio | Colmena Beta Lab | `A2:04:2A:B9:C1:D9` | Multisensor |

**Evolución de la BD:**
- `abeja_net_v3.sql` → MySQL, sin biometría, sin refresh_token
- `abeja_net_v3_postgres.sql` → Migración a PostgreSQL, misma estructura
- `abeja_net_v4_postgres.sql` → **Actual**. Agrega `proveedor_auth` (local/google) y `refresh_token` en `usuarios`

---

## 3. ESQUEMA DE BASE DE DATOS OPERACIONAL (OLTP)

### Tablas principales (v4_postgres)
```sql
roles            (id SMALLSERIAL, nombre VARCHAR(20))
usuarios         (id, nombre, apellido_paterno, apellido_materno, correo, contrasena,
                  push_token, refresh_token, proveedor_auth, rol_id, esta_activo, fecha_creacion)
apiarios         (id, nombre, descripcion_general, direccion_o_coordenadas, fecha_creacion, creado_por)
colmenas         (id, apiario_id, nombre, descripcion_especifica, fecha_creacion)
usuarios_apiarios (usuario_id, apiario_id, fecha_asignacion, asignado_por_admin_id)
sensores         (id, mac_address, colmena_id, tipo_sensor, estado ENUM, fecha_instalacion, ultima_lectura_en)
lecturas_ambientales (id BIGSERIAL, sensor_id, humedad, temperatura, peso, sonido, lluvia BOOLEAN, fecha_registro)
alertas          (id, colmena_id, tipo_alerta, valor_registrado, mensaje, leida, fecha_alerta)
```

### Variables en `lecturas_ambientales` (la tabla central)
| Campo | Tipo SQL | Tipo Estadístico | Unidad | Rango esperado |
|-------|----------|-----------------|--------|----------------|
| `temperatura` | DECIMAL(5,2) | **Continua** | °C | 12 – 42 |
| `humedad` | DECIMAL(5,2) | **Continua** | % | 40 – 95 |
| `peso` | DECIMAL(6,2) | **Continua** | kg | 10 – 30 |
| `sonido` | DECIMAL(5,2) | **Continua** | dB | 40 – 75 |
| `lluvia` | BOOLEAN | **Discreta/Nominal** | 0/1 | {0, 1} |
| `sensor_id` | INTEGER | **Nominal** (ID) | — | 1..N |
| `fecha_registro` | TIMESTAMP | **Continua** (ordinal) | — | — |

### Variables derivadas (enriquecimiento en limpieza)
| Campo derivado | Tipo | Descripción |
|---------------|------|-------------|
| `hora` | Discreta | Hora del día (0-23) |
| `dia_semana` | Ordinal | 0=lunes … 6=domingo |
| `mes` | Ordinal | 1-12 |
| `semana` | Discreta | Semana del año (ISO) |
| `es_noche` | Nominal/Binaria | 1 si hora < 7 o hora ≥ 20 |
| `es_fin_semana` | Nominal/Binaria | 1 si dia_semana ≥ 5 |
| `periodo_dia` | Nominal (ordinal) | madrugada/mañana/tarde/noche |
| `tipo_sensor_enc` | Nominal codificada | LabelEncoder de tipo_sensor |

---

## 4. DISEÑO DEL DATA WAREHOUSE — STAR SCHEMA

```
                         ┌──────────────────────────┐
                         │      dim_tiempo          │
                         │  sk_tiempo (PK)          │
                         │  fecha_completa          │
                         │  año / mes / semana      │
                         │  dia_semana / nombre_dia │
                         │  hora / periodo_dia      │
                         │  es_noche / es_fin_semana│
                         │  es_hora_activa_abejas   │
                         └────────────┬─────────────┘
                                      │
   ┌─────────────────┐   ┌────────────▼──────────────┐   ┌─────────────────────┐
   │   dim_sensor    │   │   fact_lecturas_ambient.  │   │    dim_colmena      │
   │  sk_sensor (PK) ├──►│   id_lectura (PK)         │◄──┤  sk_colmena (PK)   │
   │  sensor_id (NK) │   │   sk_sensor  (FK)         │   │  colmena_id (NK)   │
   │  mac_address    │   │   sk_tiempo  (FK)         │   │  nombre_colmena    │
   │  tipo_sensor    │   │   sk_colmena (FK)         │   │  descripcion       │
   │  estado         │   │   sk_apiario (FK)         │   │  fecha_creacion    │
   │  fecha_install. │   │   ─── MÉTRICAS ───         │   └─────────────────────┘
   │  colmena_nombre │   │   temperatura  (DECIMAL)  │
   │  apiario_nombre │   │   humedad      (DECIMAL)  │   ┌─────────────────────┐
   └─────────────────┘   │   peso         (DECIMAL)  │   │    dim_apiario      │
                         │   sonido       (DECIMAL)  │◄──┤  sk_apiario (PK)   │
                         │   lluvia       (INT 0/1)  │   │  apiario_id (NK)   │
                         │   alerta_temp  (INT 0/1)  │   │  nombre_apiario    │
                         └───────────────────────────┘   │  descripcion_gen.  │
                                                          │  coordenadas       │
                                                          └─────────────────────┘
```

**Justificación del Esquema en Estrella:**
- **Tabla de hechos:** `fact_lecturas_ambientales` con métricas numéricas y FK a 4 dimensiones.
- **Granularidad:** una lectura cada 15 minutos por sensor (cada ESP32 envía datos c/10 min en producción).
- **Dimensiones degeneradas:** `lluvia` y `alerta_temperatura` se mantienen en la tabla de hechos por ser binarias y de baja cardinalidad.

**Parámetros de configuración PostgreSQL (local):**
```sql
-- Índices principales recomendados para el DW
CREATE INDEX idx_fact_tiempo   ON fact_lecturas_ambientales (sk_tiempo);
CREATE INDEX idx_fact_sensor   ON fact_lecturas_ambientales (sk_sensor);
CREATE INDEX idx_fact_colmena  ON fact_lecturas_ambientales (sk_colmena);
CREATE INDEX idx_dim_tiempo_fecha ON dim_tiempo (fecha_completa);

-- Parámetros de postgresql.conf sugeridos para análisis local
-- shared_buffers     = 256MB
-- work_mem           = 64MB
-- effective_cache_size = 1GB
-- max_parallel_workers_per_gather = 2
```

---

## 5. FUENTES DE DATOS Y CALIDAD

### Fuentes del dataset
| Fuente | Tipo | Formato | Descripción |
|--------|------|---------|-------------|
| ESP32 vía POST `/api/sensor-data` | Estructurada | JSON → PostgreSQL | Lecturas en tiempo real de sensores |
| `generate_mock_data.js` | Sintética | JS → PostgreSQL | Simulación de 30 días para testing |
| `00_generar_datos.py` | Sintética | Python → CSV | Dataset para esta práctica |
| `abeja_net_v4_postgres.sql` | Estructurada | SQL | Esquema + datos semilla de la BD |

### Referencia científica para rangos de normalidad en colmenas de *Apis mellifera*
| Variable | Rango normal | Rango de alerta | Fuente |
|----------|-------------|-----------------|--------|
| Temperatura interior | 32–36°C | <15°C o >40°C | Owens, 1971; Seeley, 1985 |
| Humedad | 40–80% | >90% (riesgo hongos) | Pirk et al., 2010 |
| Peso diario (neto) | +0.05 a +0.3 kg/día | Pérdida >0.5 kg/día | Meikle et al., 2008 |
| Sonido (actividad normal) | 42–65 dB | >70 dB (enjambre) | Robles-Guerrero et al., 2020 |

---

## 6. PROBLEMAS DE CALIDAD INTRODUCIDOS EN `00_generar_datos.py`

| # | Problema | % afectado | Técnica de limpieza |
|---|---------|-----------|---------------------|
| 1 | Nulos en humedad | ~5% | Forward fill por grupo de sensor |
| 2 | Nulos en temperatura | ~4% | Forward fill por grupo de sensor |
| 3 | Nulos en sonido | ~3% | Forward fill por grupo de sensor |
| 4 | Outliers: temp > 45°C o < 0°C | ~1% | Invalidar → NaN → imputar |
| 5 | Outliers: humedad > 100% | ~0.8% | Invalidar → NaN → imputar |
| 6 | Registros duplicados | ~1.5% | `drop_duplicates(subset=['sensor_id','fecha_registro'])` |
| 7 | Formato incorrecto en `lluvia` ("si"/"no" como string) | ~4% | Mapeo a 0/1 entero |
| 8 | `sensor_id` nulo (registro huérfano) | ~0.8% | Eliminar fila (no identificable) |

---

## 7. ESTRATEGIA DE SELECCIÓN DE CARACTERÍSTICAS (AU)

**Variable objetivo (target):** `alerta_temperatura` = 1 si temperatura > 35°C
- Justificación biológica: por encima de 35°C las abejas de ventilación (fanners) se activan masivamente, lo que correlaciona con mayor sonido, menor humedad y potencial pérdida de peso.

**Pipeline de selección:**
1. **Correlación de Pearson** → eliminar features con |r| < 0.02 con el target
2. **Umbral de Varianza** → eliminar features cuasi-constantes (var < 0.01)
3. **Chi-Cuadrado (χ²)** → evaluar significancia estadística de variables categóricas/binarias
4. **Random Forest Importance** → ranking final; retener features con importancia ≥ 0.02

**Features evaluadas:**
`humedad, peso, sonido, lluvia, hora, dia_semana, es_noche, es_fin_semana, mes, tipo_sensor_enc, periodo_dia_enc`

---

## 8. ESTRUCTURA DE ARCHIVOS DE LA PRÁCTICA

```
practica_preprocesamiento/
├── context.md                         ← Este archivo (referencia completa)
├── 00_generar_datos.py                ← Genera data/raw/lecturas_crudas.csv
├── 01_sa_arquitectura_dw.md           ← Documento SA completo
├── 02_de_limpieza_pipeline.py         ← Pipeline DE paso a paso
├── 03_au_seleccion_caracteristicas.py ← Feature selection AU
├── requirements.txt                   ← pandas, numpy, scikit-learn, matplotlib, seaborn
└── data/
    ├── raw/
    │   └── lecturas_crudas.csv        ← Generado por 00_
    └── clean/
        ├── lecturas_limpias.csv       ← Generado por 02_
        └── dataset_final_features.csv ← Generado por 03_
```

---

## 9. CÓMO EJECUTAR

```bash
# 1. Instalar dependencias (una sola vez)
pip install -r requirements.txt

# 2. Generar dataset sintético sucio (OBLIGATORIO primero)
python 00_generar_datos.py

# 3. SA — Revisar el documento de arquitectura
# (ver 01_sa_arquitectura_dw.md)

# 4. DE — Ejecutar pipeline de limpieza
python 02_de_limpieza_pipeline.py

# 5. AU — Selección de características
python 03_au_seleccion_caracteristicas.py
```

> **Nota:** Los scripts 02 y 03 deben ejecutarse desde la carpeta `practica_preprocesamiento/`.

---

## 10. NOTAS PARA SESIONES FUTURAS

- La BD en Render **no está corriendo actualmente** (plan gratuito duerme o fue suspendida). Para esta práctica se trabaja 100% con datos sintéticos en CSV local.
- El script `backend/generate_mock_data.js` es la referencia original de simulación de sensores; `00_generar_datos.py` lo porta a Python con problemas de calidad adicionales.
- Si en el futuro se levanta la BD, se puede exportar `lecturas_ambientales` con `\COPY` desde psql y reemplazar `data/raw/lecturas_crudas.csv` para repetir el pipeline con datos reales.
- Las constantes de simulación (temperatura base 20°C, variación 14°C, ciclo coseno diario) están documentadas en `backend/generate_mock_data.js` líneas 36-62.
- El objetivo AU (selección de características) produce `dataset_final_features.csv` que puede usarse directamente para entrenar un modelo de clasificación (Prophet, XGBoost, LSTM) en una práctica futura.
