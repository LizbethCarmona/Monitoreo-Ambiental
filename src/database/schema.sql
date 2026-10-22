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
-- Referencias revisadas: NOM-025-SSA1-2021 (PM2.5), NOM-010-STPS-2014 (CO2)
-- y NOM-015-STPS-2001 (estrés térmico ocupacional). No son límites universales para
-- lecturas sintéticas ambientales; NOM-015 requiere ITGBH y regimen de trabajo.
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

-- REFERENCIAS Y LIMITACIONES:
--  * PM2.5: NOM-025-SSA1-2021, Tabla 1, fija una transicion para el promedio de 24 h:
--    41 (Año 1), 33 (Año 3) y 25 ug/m3 (Año 5). Para 2026-10-14 se usa la fase Año 5.
--    La NOM no define niveles de alerta "advertencia/critico" para lecturas instantaneas.
--  * CO2: NOM-010-STPS-2014, Apendice I, Tabla I.1 (PDF p. 53): VLE-PPT 5,000 ppm y
--    VLE-CT 30,000 ppm; este ultimo aplica a un periodo de hasta 15 minutos en centros de
--    trabajo, no a una lectura instantanea. El numeral 4.29 define el nivel de accion como
--    la mitad del VLE-PPT (2,500 ppm); es una referencia ocupacional, no alerta ambiental.
--  * Temperatura: NOM-015-STPS-2001 regula estres termico mediante ITGBH, carga de trabajo
--    y regimen de exposicion/recuperacion (Tabla 1, PDF p. 5). Los sensores miden aire, no
--    ITGBH; por ello 30.0/32.2 C solo son heuristicas provisionales del proyecto.
--  * Los limites puntuales PM2.5 (35/75), CO2 instantaneo (30,000) y temperatura (30/32.2)
--    son criterios de demostracion; no determinan cumplimiento normativo.
-- Fuentes oficiales:
-- NOM-025: https://www.dof.gob.mx/nota_detalle.php?codigo=5633855&fecha=27/10/2021
-- NOM-010: https://www.gob.mx/cms/uploads/attachment/file/680155/NOM-010-STPS-2014.pdf
--          https://dof.gob.mx/normasOficiales/5359/stps2a11_C/stps2a11_C.html
-- NOM-015: https://www.stps.gob.mx/bp/secciones/dgsst/normatividad/normas/Nom-015.pdf
INSERT IGNORE INTO umbrales (metrica, nivel, aplica_a, valor_limite, fuente) VALUES
  ('pm25', 'critico',     'promedio_24h', 25.00,    'NOM-025-SSA1-2021, Tabla 1, fase Año 5 (2026-10-14)'),
  ('pm25', 'advertencia', 'lectura',      35.00,    'PROVISIONAL (definido por el equipo)'),
  ('pm25', 'critico',     'lectura',      75.00,    'PROVISIONAL (definido por el equipo)'),
  ('co2',  'advertencia', 'promedio_8h',  2500.00,  'Referencia NOM-010-STPS-2014 4.29; uso ambiental provisional'),
  ('co2',  'critico',     'promedio_8h',  5000.00,  'Referencia NOM-010-STPS-2014 Tabla I.1; uso ambiental provisional'),
  ('co2',  'critico',     'lectura',      30000.00, 'PROVISIONAL: VLE-CT requiere periodo de hasta 15 min'),
  ('tmp',  'advertencia', 'lectura',      30.00,    'PROVISIONAL: aire; NOM-015 evalua ITGBH ocupacional'),
  ('tmp',  'critico',     'lectura',      32.20,    'PROVISIONAL: aire; NOM-015 evalua ITGBH ocupacional');

-- ---------------------------------------------------------------------
-- EJEMPLO: insercion transaccional (lo que hara DatabaseManager en la semana 4)
-- ---------------------------------------------------------------------
-- START TRANSACTION;
--   INSERT INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura)
--   VALUES ('sensor_03', 85.0, 780, 31.4, '2026-09-24 16:48:00.000');
--   INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, valor_medido, valor_limite, mensaje)
--   VALUES (LAST_INSERT_ID(), 'sensor_03', 'pm25', 'critico', 85.0, 75.0, 'PM2.5 sobre umbral critico');
-- COMMIT;
