-- =====================================================================
-- Proyecto: Monitoreo ambiental en tiempo real (ODS 11 y 13)
-- Esquema relacional MySQL 8 (InnoDB) - BORRADOR v0.1 para revisar con el equipo
-- Fuente: JSON de metricas (sensor_id, pm2.5, co2, tmp, timestamp) y UML
-- Nota: el JSON usa la clave "pm2.5"; en SQL la columna se llama pm25
--       (el punto no es valido en nombres de columna).
-- Todos los timestamps se guardan en UTC (ISO 8601 del JSON).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS monitoreo_ambiental
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE monitoreo_ambiental;

-- ---------------------------------------------------------------------
-- 1. SENSORES: catalogo de dispositivos IoT
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sensores (
  sensor_id       VARCHAR(50)  NOT NULL,              -- ej. 'sensor_01'
  nombre          VARCHAR(100) NULL,
  ubicacion       VARCHAR(150) NULL,
  latitud         DECIMAL(9,6) NULL,
  longitud        DECIMAL(9,6) NULL,
  activo          BOOLEAN      NOT NULL DEFAULT TRUE,
  fecha_registro  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (sensor_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. LECTURAS: serie temporal (tabla de mayor volumen de escritura)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lecturas (
  lectura_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sensor_id          VARCHAR(50)     NOT NULL,
  pm25               DECIMAL(6,2)    NOT NULL,          -- ug/m3
  co2                DECIMAL(7,2)    NOT NULL,          -- ppm
  tmp                DECIMAL(5,2)    NOT NULL,          -- grados Celsius
  timestamp_lectura  DATETIME(3)     NOT NULL,          -- viene del sensor (UTC)
  timestamp_ingesta  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3), -- cuando la recibio el servidor
  PRIMARY KEY (lectura_id),
  -- Evita duplicados si un hilo reintenta el INSERT (idempotencia)
  UNIQUE KEY uq_sensor_momento (sensor_id, timestamp_lectura),
  -- Indices temporales para consultas historicas y agregados
  KEY idx_lecturas_tiempo (timestamp_lectura),
  CONSTRAINT fk_lecturas_sensor
    FOREIGN KEY (sensor_id) REFERENCES sensores (sensor_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. UMBRALES: limites configurables por metrica (evita hardcodear en C++)
-- ---------------------------------------------------------------------
-- aplica_a: 'lectura'      = se compara contra cada lectura puntual del sensor
--           'promedio_8h'  = se compara contra el promedio movil de 8 horas (NOM-010, CO2)
--           'promedio_24h' = se compara contra el promedio movil de 24 horas (NOM-025, PM2.5)
-- fuente:   de donde sale el limite (norma o 'PROVISIONAL' si lo definio el equipo)
-- Normas aprobadas por el profesor: NOM-025-SSA1-2021 (PM2.5), NOM-010-STPS-2014 (CO2)
-- y NOM-015-STPS-2001 (temperatura). Las dos ultimas son normas laborales.
CREATE TABLE IF NOT EXISTS umbrales (
  umbral_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  metrica      ENUM('pm25','co2','tmp') NOT NULL,
  nivel        ENUM('advertencia','critico') NOT NULL,
  aplica_a     ENUM('lectura','promedio_8h','promedio_24h') NOT NULL DEFAULT 'lectura',
  valor_limite DECIMAL(8,2)  NOT NULL,
  fuente       VARCHAR(150)  NOT NULL DEFAULT 'PROVISIONAL',
  PRIMARY KEY (umbral_id),
  UNIQUE KEY uq_metrica_nivel_aplica (metrica, nivel, aplica_a)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. ALERTAS: eventos generados cuando una lectura supera un umbral
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alertas (
  alerta_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lectura_id        BIGINT UNSIGNED NOT NULL,
  sensor_id         VARCHAR(50)     NOT NULL,
  metrica           ENUM('pm25','co2','tmp') NOT NULL,
  nivel             ENUM('advertencia','critico') NOT NULL,
  valor_medido      DECIMAL(8,2)    NOT NULL,
  valor_limite      DECIMAL(8,2)    NOT NULL,
  mensaje           VARCHAR(255)    NULL,
  timestamp_alerta  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  atendida          BOOLEAN         NOT NULL DEFAULT FALSE,
  PRIMARY KEY (alerta_id),
  KEY idx_alertas_tiempo (timestamp_alerta),
  KEY idx_alertas_sensor_tiempo (sensor_id, timestamp_alerta),
  KEY idx_alertas_activas (atendida, nivel),
  CONSTRAINT fk_alertas_lectura
    FOREIGN KEY (lectura_id) REFERENCES lecturas (lectura_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_alertas_sensor
    FOREIGN KEY (sensor_id) REFERENCES sensores (sensor_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- DATOS INICIALES (valores PLACEHOLDER: confirmar con el equipo/PO)
-- ---------------------------------------------------------------------
INSERT IGNORE INTO sensores (sensor_id, nombre) VALUES
  ('sensor_01', 'Sensor 01'),
  ('sensor_02', 'Sensor 02'),
  ('sensor_03', 'Sensor 03');

-- LIMITES POR NORMA (aprobadas por el profesor):
--  * PM2.5: NOM-025-SSA1-2021, 41 ug/m3 en promedio de 24 h (verificar valor final en el DOF).
--  * CO2:   NOM-010-STPS-2014. VLE-PPT = 5,000 ppm (promedio 8 h) y VLE-CT = 30,000 ppm (15 min).
--           La Tabla 17 de la norma toma 0.50 x VLE como nivel que obliga a actuar,
--           por eso advertencia = 2,500 ppm. Confirmar valores en la Tabla I.1 del DOF.
--  * Temp:  NOM-015-STPS-2001. Tabla 1 (ITGBH, regimen ligero, 100% exposicion) = 30.0 C;
--           numeral 7.3.5: arriba de 32.2 C solo se permite exposicion momentanea.
--           LIMITACION: la norma usa el indice ITGBH (requiere humedad y temperatura de
--           globo); los sensores solo miden temperatura del aire, que se usa como aproximacion.
-- Los limites PM2.5 por lectura (35 y 75) son PROVISIONALES: la norma solo fija promedio de 24 h.
INSERT IGNORE INTO umbrales (metrica, nivel, aplica_a, valor_limite, fuente) VALUES
  ('pm25', 'critico',     'promedio_24h', 41.00,    'NOM-025-SSA1-2021 (verificar en DOF)'),
  ('pm25', 'advertencia', 'lectura',      35.00,    'PROVISIONAL (definido por el equipo)'),
  ('pm25', 'critico',     'lectura',      75.00,    'PROVISIONAL (definido por el equipo)'),
  ('co2',  'advertencia', 'promedio_8h',  2500.00,  'NOM-010-STPS-2014: 0.50 x VLE-PPT (Tabla 17)'),
  ('co2',  'critico',     'promedio_8h',  5000.00,  'NOM-010-STPS-2014: VLE-PPT (Apendice I)'),
  ('co2',  'critico',     'lectura',      30000.00, 'NOM-010-STPS-2014: VLE-CT (Apendice I)'),
  ('tmp',  'advertencia', 'lectura',      30.00,    'NOM-015-STPS-2001: Tabla 1, regimen ligero 100%'),
  ('tmp',  'critico',     'lectura',      32.20,    'NOM-015-STPS-2001: numeral 7.3.5');

-- ---------------------------------------------------------------------
-- EJEMPLO: insercion transaccional (lo que hara DatabaseManager en la semana 4)
-- ---------------------------------------------------------------------
-- START TRANSACTION;
--   INSERT INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura)
--   VALUES ('sensor_03', 85.0, 780, 31.4, '2026-09-24 16:48:00.000');
--   INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, valor_medido, valor_limite, mensaje)
--   VALUES (LAST_INSERT_ID(), 'sensor_03', 'pm25', 'critico', 85.0, 75.0, 'PM2.5 sobre umbral critico');
-- COMMIT;
