-- =====================================================================
-- Semana 4 - Datos de prueba masivos (volumen) para monitoreo_ambiental
-- Genera N sensores x M lecturas, y alertas para lecturas criticas de PM2.5.
-- Requiere haber corrido schema.sql antes.
-- Uso:   CALL generar_datos_prueba(50, 2000);   -- 50 sensores x 2000 = 100,000 lecturas
-- Limpieza: CALL limpiar_datos_prueba();
-- ATENCION: los datos son ALEATORIOS, solo para pruebas de rendimiento.
-- =====================================================================
USE monitoreo_ambiental;

DROP PROCEDURE IF EXISTS generar_datos_prueba;
DROP PROCEDURE IF EXISTS limpiar_datos_prueba;

DELIMITER $$

CREATE PROCEDURE generar_datos_prueba(IN p_sensores INT, IN p_lecturas INT)
BEGIN
  DECLARE v_base DATETIME(3);
  SET SESSION cte_max_recursion_depth = 1000000;
  SET v_base = UTC_TIMESTAMP(3);

  -- 1) Sensores sensor_01 ... sensor_NN
  INSERT IGNORE INTO sensores (sensor_id, nombre)
  WITH RECURSIVE s(n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM s WHERE n < p_sensores
  )
  SELECT CONCAT('sensor_', LPAD(n, 2, '0')), CONCAT('Sensor ', LPAD(n, 2, '0')) FROM s;

  -- 2) Lecturas: una cada 5 segundos hacia el pasado, por sensor
  INSERT IGNORE INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura)
  WITH RECURSIVE
    s(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM s WHERE n < p_sensores),
    m(k) AS (SELECT 1 UNION ALL SELECT k + 1 FROM m WHERE k < p_lecturas)
  SELECT CONCAT('sensor_', LPAD(s.n, 2, '0')),
         ROUND(10 + RAND() * 90, 2),     -- pm25: 10 a 100 ug/m3
         ROUND(400 + RAND() * 700, 2),   -- co2: 400 a 1100 ppm
         ROUND(18 + RAND() * 17, 2),     -- tmp: 18 a 35 C
         v_base - INTERVAL (m.k * 5) SECOND
  FROM s CROSS JOIN m;

  -- 3) Alertas para lecturas de PM2.5 sobre el umbral critico (por lectura)
  INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, valor_medido, valor_limite, mensaje)
  SELECT l.lectura_id, l.sensor_id, 'pm25', 'critico', l.pm25, u.valor_limite,
         'PM2.5 sobre umbral critico (dato de prueba)'
  FROM lecturas l
  JOIN umbrales u
    ON u.metrica = 'pm25' AND u.nivel = 'critico' AND u.aplica_a = 'lectura'
  LEFT JOIN alertas a ON a.lectura_id = l.lectura_id
  WHERE l.pm25 >= u.valor_limite AND a.alerta_id IS NULL;

  SELECT (SELECT COUNT(*) FROM sensores) AS sensores,
         (SELECT COUNT(*) FROM lecturas) AS lecturas,
         (SELECT COUNT(*) FROM alertas)  AS alertas;
END$$

CREATE PROCEDURE limpiar_datos_prueba()
BEGIN
  -- Borra todo lo de lecturas/alertas y los sensores de prueba (> sensor_03)
  -- Cada DELETE filtra por una columna clave (> 0) para que funcione con el
  -- "Safe Updates" de Workbench (error 1175).
  DELETE FROM alertas WHERE alerta_id > 0;
  DELETE FROM lecturas WHERE lectura_id > 0;
  DELETE FROM sensores WHERE sensor_id NOT IN ('sensor_01','sensor_02','sensor_03');
  ALTER TABLE lecturas AUTO_INCREMENT = 1;
  ALTER TABLE alertas  AUTO_INCREMENT = 1;
END$$

DELIMITER ;

-- =====================================================================
-- CONSULTAS PARA VERIFICAR RENDIMIENTO E INDICES (correr despues de CALL ...)
-- =====================================================================

-- A) Promedio movil de 24 h por sensor (lo que compara la norma de PM2.5)
-- SELECT sensor_id, ROUND(AVG(pm25),2) AS pm25_prom_24h
-- FROM lecturas
-- WHERE timestamp_lectura >= UTC_TIMESTAMP(3) - INTERVAL 24 HOUR
-- GROUP BY sensor_id;

-- B) Alertas activas mas recientes (lo que mostraria la API /alertas)
-- SELECT * FROM alertas WHERE atendida = FALSE ORDER BY timestamp_alerta DESC LIMIT 20;

-- C) Ver si usa el indice temporal (revisar columna "key" y "rows")
-- EXPLAIN SELECT * FROM lecturas
-- WHERE sensor_id = 'sensor_10'
--   AND timestamp_lectura >= UTC_TIMESTAMP(3) - INTERVAL 1 HOUR;
