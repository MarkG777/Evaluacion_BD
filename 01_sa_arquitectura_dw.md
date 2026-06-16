# SA — Documento de Arquitectura y Repositorio Preprocesado
## AbejaNet — Extracción de Conocimiento en Bases de Datos

---

## 1. Descripción del Caso de Estudio

**Proyecto:** AbejaNet Revival — Sistema IoT de monitoreo de colmenas de abejas  
**Contexto:** Plataforma que integra sensores ESP32 instalados en colmenas para recopilar variables ambientales en tiempo real (temperatura, humedad, peso, nivel de sonido y lluvia), y expone estos datos a través de una API REST consumida por una aplicación móvil (React Native/Expo) y un panel web de administración.

**Objetivo de la práctica:** Construir un Data Warehouse a partir de la base de datos operacional del sistema IoT y demostrar técnicas de preprocesamiento para preparar un dataset listo para Machine Learning.

---

## 2. Esquema de Data Warehouse — Estrella (Star Schema)

### Justificación del modelo elegido
Se eligió el **Esquema en Estrella** porque:
- La tabla de hechos central (`fact_lecturas_ambientales`) tiene métricas numéricas claras y bien definidas.
- Las dimensiones (sensor, tiempo, colmena, apiario) son de lectura frecuente y cambios lentos (Slowly Changing Dimensions tipo 1).
- El esquema estrella es más eficiente para queries analíticas OLAP que el modelo copo de nieve.

### Diagrama Conceptual

```
                       ┌─────────────────────────────┐
                       │         dim_tiempo          │
                       ├─────────────────────────────┤
                       │ sk_tiempo          PK       │
                       │ fecha_completa  TIMESTAMP   │
                       │ año             SMALLINT    │
                       │ mes             SMALLINT    │
                       │ nombre_mes      VARCHAR(15) │
                       │ semana_año      SMALLINT    │
                       │ dia_mes         SMALLINT    │
                       │ dia_semana      SMALLINT    │
                       │ nombre_dia      VARCHAR(10) │
                       │ hora            SMALLINT    │
                       │ periodo_dia     VARCHAR(12) │
                       │ es_noche        BOOLEAN     │
                       │ es_fin_semana   BOOLEAN     │
                       │ es_hora_activa  BOOLEAN     │
                       └──────────────┬──────────────┘
                                      │ FK sk_tiempo
         ┌──────────────────┐         │
         │   dim_sensor     │         │
         ├──────────────────┤   ┌─────▼────────────────────────┐
         │ sk_sensor    PK  ├──►│  fact_lecturas_ambientales   │
         │ sensor_id    NK  │   ├──────────────────────────────┤
         │ mac_address      │   │ id_lectura    BIGSERIAL  PK  │
         │ tipo_sensor      │   │ sk_sensor     INTEGER    FK  │
         │ estado           │   │ sk_tiempo     INTEGER    FK  │
         │ fecha_instalacion│   │ sk_colmena    INTEGER    FK  │
         └──────────────────┘   │ sk_apiario    INTEGER    FK  │
                                │ ─── MÉTRICAS ───             │
         ┌──────────────────┐   │ temperatura   DECIMAL(5,2)  │
         │   dim_colmena    │   │ humedad       DECIMAL(5,2)  │
         ├──────────────────┤   │ peso          DECIMAL(6,2)  │
         │ sk_colmena   PK  ├──►│ sonido        DECIMAL(5,2)  │
         │ colmena_id   NK  │   │ lluvia        SMALLINT 0/1  │
         │ nombre_colmena   │   │ alerta_temp   SMALLINT 0/1  │
         │ descripcion      │   └──────────────┬───────────────┘
         │ fecha_creacion   │                  │
         └──────────────────┘                  │ FK sk_apiario
                                               │
         ┌──────────────────────────────────────▼────────┐
         │                 dim_apiario                   │
         ├───────────────────────────────────────────────┤
         │ sk_apiario           PK                       │
         │ apiario_id           NK  (natural key)        │
         │ nombre_apiario       VARCHAR(150)             │
         │ descripcion_general  TEXT                     │
         │ coordenadas          VARCHAR(255)             │
         │ fecha_creacion       TIMESTAMP                │
         └───────────────────────────────────────────────┘
```

### Definición de Tablas del DW

#### `fact_lecturas_ambientales` (Tabla de Hechos)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id_lectura` | BIGSERIAL PK | Clave surrogate de la lectura |
| `sk_sensor` | INTEGER FK | → `dim_sensor` |
| `sk_tiempo` | INTEGER FK | → `dim_tiempo` |
| `sk_colmena` | INTEGER FK | → `dim_colmena` |
| `sk_apiario` | INTEGER FK | → `dim_apiario` |
| `temperatura` | DECIMAL(5,2) | °C interior de la colmena |
| `humedad` | DECIMAL(5,2) | % de humedad relativa |
| `peso` | DECIMAL(6,2) | kg totales de la colmena (NULL si no aplica) |
| `sonido` | DECIMAL(5,2) | dB de actividad sonora |
| `lluvia` | SMALLINT | 1=lluvia, 0=sin lluvia |
| `alerta_temp` | SMALLINT | 1 si temperatura > 35°C (calculado) |

**Granularidad:** Una fila = una lectura de un sensor cada 15 minutos.

#### `dim_tiempo`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `sk_tiempo` | SERIAL PK | Surrogate key |
| `fecha_completa` | TIMESTAMP | Timestamp completo de la lectura |
| `año` | SMALLINT | 2025, 2026… |
| `mes` | SMALLINT | 1-12 |
| `nombre_mes` | VARCHAR(15) | Enero, Febrero… |
| `semana_año` | SMALLINT | Semana ISO del año |
| `dia_mes` | SMALLINT | 1-31 |
| `dia_semana` | SMALLINT | 0=lunes … 6=domingo |
| `nombre_dia` | VARCHAR(10) | Lunes, Martes… |
| `hora` | SMALLINT | 0-23 |
| `periodo_dia` | VARCHAR(12) | madrugada/mañana/tarde/noche |
| `es_noche` | BOOLEAN | TRUE si hora < 7 o hora ≥ 20 |
| `es_fin_semana` | BOOLEAN | TRUE si dia_semana ≥ 5 |
| `es_hora_activa` | BOOLEAN | TRUE si 7 ≤ hora < 20 (abejas activas) |

#### `dim_sensor`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `sk_sensor` | SERIAL PK | Surrogate key |
| `sensor_id` | INTEGER NK | ID natural de la BD operacional |
| `mac_address` | VARCHAR(17) | Dirección MAC del ESP32 |
| `tipo_sensor` | VARCHAR(50) | Temperatura/Humedad, Multisensor |
| `estado` | VARCHAR(20) | activo/inactivo/mantenimiento/no_asignado |
| `fecha_instalacion` | TIMESTAMP | Cuándo fue instalado |

#### `dim_colmena`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `sk_colmena` | SERIAL PK | Surrogate key |
| `colmena_id` | INTEGER NK | ID natural de la BD operacional |
| `nombre_colmena` | VARCHAR(100) | Nombre descriptivo |
| `descripcion` | TEXT | Descripción específica |
| `fecha_creacion` | TIMESTAMP | Registro inicial |

#### `dim_apiario`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `sk_apiario` | SERIAL PK | Surrogate key |
| `apiario_id` | INTEGER NK | ID natural de la BD operacional |
| `nombre_apiario` | VARCHAR(150) | Nombre del apiario |
| `descripcion_general` | TEXT | Descripción |
| `coordenadas` | VARCHAR(255) | Latitud/Longitud |

---

## 3. Inventario de Fuentes y Tipos de Datos

### Fuentes de Datos
| # | Fuente | Tipo | Formato | Frecuencia |
|---|--------|------|---------|-----------|
| 1 | ESP32 vía POST `/api/sensor-data` | Estructurada en tiempo real | JSON | Cada 10 min |
| 2 | `backend/generate_mock_data.js` | Sintética estructurada | JS → PostgreSQL | Bajo demanda |
| 3 | `00_generar_datos.py` (esta práctica) | Sintética estructurada | Python → CSV | Bajo demanda |
| 4 | `abeja_net_v4_postgres.sql` | Estructurada relacional | SQL Script | Inicial/migraciones |

### Clasificación de Variables por Tipo
| Variable | Tipo Estadístico | Escala | Unidad | Valores posibles |
|----------|-----------------|--------|--------|-----------------|
| `temperatura` | **Continua** | Razón | °C | [−∞, +∞] (biológico: 0–45) |
| `humedad` | **Continua** | Razón | % | [0, 100] |
| `peso` | **Continua** | Razón | kg | [0, +∞] |
| `sonido` | **Continua** | Razón | dB | [20, 120] (biológico: 40–80) |
| `lluvia` | **Discreta / Nominal** | Nominal binaria | — | {0, 1} |
| `sensor_id` | **Discreta / Nominal** | Nominal (ID) | — | {1, 2, 3, …} |
| `tipo_sensor` | **Categórica / Nominal** | Nominal | — | {Temperatura/Humedad, Multisensor} |
| `estado` (sensor) | **Categórica / Ordinal** | Ordinal | — | {activo, mantenimiento, inactivo, no_asignado} |
| `hora` | **Discreta / Cíclica** | Intervalo cíclico | h | [0, 23] |
| `dia_semana` | **Discreta / Ordinal** | Ordinal cíclico | — | [0, 6] |
| `mes` | **Discreta / Ordinal** | Ordinal cíclico | — | [1, 12] |
| `es_noche` | **Discreta / Nominal** | Nominal binaria | — | {0, 1} |
| `es_fin_semana` | **Discreta / Nominal** | Nominal binaria | — | {0, 1} |
| `alerta_temp` | **Discreta / Nominal** | Nominal binaria (target) | — | {0, 1} |

---

## 4. Técnicas de Limpieza de Datos

### 4.1 Detección e imputación de valores nulos
**Regla:** Variables numéricas de series temporales usan **forward fill (ffill)** por grupo de sensor, seguido de **backward fill (bfill)** como respaldo. Esto es apropiado porque los sensores producen lecturas casi continuas y el valor más cercano en el tiempo es la mejor estimación.

**Justificación:** El relleno por media global ignoraría la estructura temporal; el ffill respeta la autocorrelación de la serie.

### 4.2 Eliminación de duplicados
**Regla:** Se eliminan filas con el mismo par `(sensor_id, fecha_registro)`, conservando la primera ocurrencia. También se eliminan duplicados exactos en todas las columnas.

**Causa de duplicados:** El ESP32 puede re-enviar datos si no recibe ACK del servidor, o el script `populate-data` puede ejecutarse dos veces.

### 4.3 Tratamiento de outliers
**Método:** Reglas de negocio combinadas con IQR para diagnóstico:
- `temperatura`: valores fuera de [0°C, 45°C] → invalidar (NaN) y luego imputar con ffill. Rango fisiológico de colmena según Owens (1971): interior 32–36°C, exterior puede variar más.
- `humedad`: valores fuera de [0%, 100%] → físicamente imposibles → NaN.
- `sonido`: valores fuera de [20 dB, 100 dB] → fuera del rango del sensor → NaN.

### 4.4 Corrección de formatos
- **`lluvia`:** Puede llegar como `True/False` (Python bool), `"si"/"no"` (string), `1/0` (entero). Se normaliza todo a `SMALLINT` {0, 1}.
- **`fecha_registro`:** Se fuerza a `datetime64[ns]` con `pd.to_datetime(errors='coerce')`.
- **`sensor_id`:** Se fuerza a `Int64` (nullable integer) para detectar NaN.

### 4.5 Eliminación de registros huérfanos
**Regla:** Filas sin `sensor_id` se eliminan porque no pueden asociarse a ninguna colmena; son inútiles para el análisis.

---

## 5. Parámetros de Configuración del Data Warehouse

### Motor: PostgreSQL 16 (local)
```sql
-- Creación del esquema DW
CREATE SCHEMA abejanet_dw;

-- Tabla de hechos con particionamiento por mes (rango en fecha)
CREATE TABLE abejanet_dw.fact_lecturas_ambientales (
    id_lectura    BIGSERIAL,
    sk_sensor     INTEGER      NOT NULL,
    sk_tiempo     INTEGER      NOT NULL,
    sk_colmena    INTEGER      NOT NULL,
    sk_apiario    INTEGER      NOT NULL,
    temperatura   DECIMAL(5,2),
    humedad       DECIMAL(5,2),
    peso          DECIMAL(6,2),
    sonido        DECIMAL(5,2),
    lluvia        SMALLINT     DEFAULT 0,
    alerta_temp   SMALLINT     DEFAULT 0
) PARTITION BY RANGE (sk_tiempo);

-- Índices de optimización para JOINs OLAP
CREATE INDEX idx_fact_sk_sensor  ON abejanet_dw.fact_lecturas_ambientales (sk_sensor);
CREATE INDEX idx_fact_sk_tiempo  ON abejanet_dw.fact_lecturas_ambientales (sk_tiempo);
CREATE INDEX idx_fact_sk_colmena ON abejanet_dw.fact_lecturas_ambientales (sk_colmena);

-- Índice de tiempo para rangos temporales
CREATE INDEX idx_dim_tiempo_fecha ON abejanet_dw.dim_tiempo (fecha_completa);
CREATE INDEX idx_dim_tiempo_hora  ON abejanet_dw.dim_tiempo (hora, es_noche);
```

### Parámetros sugeridos en `postgresql.conf` (análisis local)
| Parámetro | Valor sugerido | Motivo |
|-----------|---------------|--------|
| `shared_buffers` | 512MB | Cache de páginas de BD |
| `work_mem` | 64MB | Por query de ordenamiento/hash |
| `effective_cache_size` | 2GB | Estimación de cache del SO |
| `max_parallel_workers_per_gather` | 4 | Paralelismo en scans |
| `enable_partitionwise_join` | on | JOINs entre particiones |
| `checkpoint_completion_target` | 0.9 | Suavizado de escritura |

---

## 6. Repositorio y Entregable Técnico

### Estructura del repositorio
```
practica_preprocesamiento/
├── context.md                          ← Documentación completa de la práctica
├── 00_generar_datos.py                 ← Generación del dataset sintético
├── 01_sa_arquitectura_dw.md            ← Este documento (SA)
├── 02_de_limpieza_pipeline.py          ← Pipeline de limpieza (DE)
├── 03_au_seleccion_caracteristicas.py  ← Feature selection (AU)
├── requirements.txt                    ← Dependencias Python
└── data/
    ├── raw/
    │   └── lecturas_crudas.csv         ← Dataset sin limpiar (8780+ filas, 13 cols)
    └── clean/
        ├── lecturas_limpias.csv        ← Dataset limpio + features temporales
        └── dataset_final_features.csv  ← Dataset optimizado para ML
```

### Estadísticas del dataset generado
| Métrica | Valor |
|---------|-------|
| Colmenas monitoreadas | 3 |
| Periodo de datos | 30 días (15 May – 14 Jun 2025) |
| Frecuencia de muestreo | Cada 15 minutos |
| Registros limpios base | 8,640 (3 × 30 × 24 × 4) |
| Registros con suciedad | ~8,770 (+ ~130 duplicados) |
| Variables originales | 13 |
| Variables tras enriquecimiento | 21 |
| Variables tras selección (AU) | ~7-9 |
