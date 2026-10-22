-- Ajustes de referencias y valores del proyecto verificados el 2026-10-14.
-- Ejecutar una vez en monitoreo_ambiental con una cuenta autorizada.
-- No borra datos. Los valores CO2/temperatura siguen siendo referencias de prototipo.
USE monitoreo_ambiental;

START TRANSACTION;

UPDATE umbrales
SET valor_limite = 25.00,
    fuente = 'NOM-025-SSA1-2021, Tabla 1, fase Año 5 (2026-10-14)'
WHERE metrica = 'pm25'
  AND nivel = 'critico'
  AND aplica_a = 'promedio_24h';

UPDATE umbrales
SET fuente = 'Referencia NOM-010-STPS-2014 4.29; uso ambiental provisional'
WHERE metrica = 'co2'
  AND nivel = 'advertencia'
  AND aplica_a = 'promedio_8h';

UPDATE umbrales
SET fuente = 'Referencia NOM-010-STPS-2014 Tabla I.1; uso ambiental provisional'
WHERE metrica = 'co2'
  AND nivel = 'critico'
  AND aplica_a = 'promedio_8h';

UPDATE umbrales
SET fuente = 'PROVISIONAL: VLE-CT requiere periodo de hasta 15 min'
WHERE metrica = 'co2'
  AND nivel = 'critico'
  AND aplica_a = 'lectura';

UPDATE umbrales
SET fuente = 'PROVISIONAL: aire; NOM-015 evalua ITGBH ocupacional'
WHERE metrica = 'tmp'
  AND aplica_a = 'lectura';

COMMIT;
