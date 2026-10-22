#!/usr/bin/env python3
"""
Semana 4 - Prueba de carga concurrente sobre monitoreo_ambiental.

Simula N sensores como N hilos. Cada hilo abre su propia conexion y guarda
lecturas dentro de una TRANSACCION (lectura + alerta si PM2.5 supera el umbral
critico), igual que lo hara DatabaseManager en C++. Tambien fuerza lecturas
duplicadas (error 1062) y reintenta ante deadlocks (error 1213).

Requisitos:  pip install mysql-connector-python
Uso:
    PowerShell: $env:MYSQL_USER = 'monitoreo_app'
               $clave = Read-Host 'Contraseña MySQL' -AsSecureString
               $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $clave).Password
    python carga_concurrente.py --sensores 20 --lecturas 500
    python carga_concurrente.py --sensores 20 --lecturas 500 --duplicados 0.1 --usuario otro_usuario

La contrasena se lee de la variable de entorno MYSQL_PASSWORD (no la escribas
en el codigo ni la subas a GitHub).
"""
import argparse
import os
import random
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import mysql.connector
from mysql.connector import errorcode, Error

LIMITE_REINTENTOS = 3


def conectar(args):
    if os.getenv("MYSQL_PASSWORD") is None:
        raise RuntimeError(
            "Falta la variable de entorno MYSQL_PASSWORD. En PowerShell, "
            "solicítala sin mostrarla con: "
            "$clave = Read-Host 'Contraseña MySQL' -AsSecureString; "
            "$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $clave).Password"
        )
    return mysql.connector.connect(
        host=args.host, port=args.puerto, user=args.usuario,
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=args.base, autocommit=False,
    )


def leer_umbral_critico(args):
    """Umbral critico de PM2.5 por lectura, tomado de la tabla umbrales."""
    conn = conectar(args)
    cur = conn.cursor()
    cur.execute(
        "SELECT valor_limite FROM umbrales "
        "WHERE metrica='pm25' AND nivel='critico' AND aplica_a='lectura'"
    )
    fila = cur.fetchone()
    conn.close()
    return float(fila[0]) if fila else 75.0


def asegurar_sensores(args, n, prefijo):
    conn = conectar(args)
    cur = conn.cursor()
    for i in range(1, n + 1):
        sid = f"{prefijo}_{i:02d}"
        cur.execute("INSERT IGNORE INTO sensores (sensor_id, nombre) VALUES (%s, %s)",
                    (sid, f"Sensor {i:02d}"))
    conn.commit()
    conn.close()


def guardar_lectura(cur, sensor_id, pm25, co2, tmp, ts, umbral):
    """Una transaccion: lectura y, si aplica, su alerta. Devuelve True si hubo alerta."""
    cur.execute(
        "INSERT INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura) "
        "VALUES (%s, %s, %s, %s, %s)", (sensor_id, pm25, co2, tmp, ts))
    hubo_alerta = pm25 >= umbral
    if hubo_alerta:
        cur.execute(
            "INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, "
            "valor_medido, valor_limite, mensaje) "
            "VALUES (LAST_INSERT_ID(), %s, 'pm25', 'critico', %s, %s, %s)",
            (sensor_id, pm25, umbral, "PM2.5 sobre umbral critico (prueba de carga)"))
    return hubo_alerta


def hilo_sensor(args, num, prefijo, umbral, base, stats, lock):
    sensor_id = f"{prefijo}_{num:02d}"
    conn = conectar(args)
    cur = conn.cursor()
    ultimo_ts = None
    local = dict(ok=0, alertas=0, duplicados=0, reintentos=0, errores=0)

    for k in range(args.lecturas):
        # Con cierta probabilidad se repite el timestamp anterior (reintento duplicado)
        if ultimo_ts is not None and random.random() < args.duplicados:
            ts = ultimo_ts
        else:
            ts = base - timedelta(seconds=(k + 1) * 5, milliseconds=num)
        pm25 = round(random.uniform(10, 100), 2)
        co2 = round(random.uniform(400, 1100), 2)
        tmp = round(random.uniform(18, 35), 2)

        for intento in range(LIMITE_REINTENTOS + 1):
            try:
                alerta = guardar_lectura(cur, sensor_id, pm25, co2, tmp, ts, umbral)
                conn.commit()
                local["ok"] += 1
                local["alertas"] += int(alerta)
                ultimo_ts = ts
                break
            except Error as e:
                conn.rollback()  # atomicidad: no queda lectura sin su alerta
                if e.errno == errorcode.ER_DUP_ENTRY:          # 1062
                    local["duplicados"] += 1
                    break
                if e.errno in (errorcode.ER_LOCK_DEADLOCK,      # 1213
                               errorcode.ER_LOCK_WAIT_TIMEOUT):  # 1205
                    local["reintentos"] += 1
                    time.sleep(0.01 * (intento + 1))
                    continue
                local["errores"] += 1
                print(f"[{sensor_id}] error inesperado {e.errno}: {e.msg}")
                break
    conn.close()
    with lock:
        for clave, valor in local.items():
            stats[clave] += valor


def verificar(args, prefijo, esperado_ok, esperado_alertas):
    """Comprueba la integridad despues de la carga."""
    conn = conectar(args)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lecturas WHERE sensor_id LIKE %s", (prefijo + "_%",))
    n_lect = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM alertas WHERE sensor_id LIKE %s AND mensaje LIKE %s",
        (prefijo + "_%", "%prueba de carga%"),
    )
    n_alert = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM alertas a LEFT JOIN lecturas l "
                "ON l.lectura_id = a.lectura_id "
                "WHERE a.sensor_id LIKE %s AND l.lectura_id IS NULL", (prefijo + "_%",))
    huerfanas = cur.fetchone()[0]
    conn.close()
    print("\n--- Verificacion de integridad ---")
    print(f"Lecturas de esta prueba:      {n_lect}  (esperadas: {esperado_ok})")
    print(f"Alertas de esta prueba:       {n_alert}  (esperadas: {esperado_alertas})")
    print(f"Alertas sin lectura (huerf.): {huerfanas}  (debe ser 0)")
    ok = (n_lect == esperado_ok and n_alert == esperado_alertas and huerfanas == 0)
    print("RESULTADO:", "OK, sin corrupcion" if ok else "REVISAR: hay inconsistencias")
    return ok


def crear_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prueba de carga concurrente (N sensores = N hilos)")
    p.add_argument("--sensores", type=int, default=10)
    p.add_argument("--lecturas", type=int, default=200, help="lecturas por sensor")
    p.add_argument("--duplicados", type=float, default=0.05,
                   help="probabilidad (0-1) de reenviar la lectura anterior")
    p.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    p.add_argument("--puerto", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    p.add_argument("--usuario", default=os.getenv("MYSQL_USER", "root"))
    p.add_argument("--base", default=os.getenv("MYSQL_DATABASE", "monitoreo_ambiental"))
    return p


def main() -> int:
    p = crear_parser()
    args = p.parse_args()
    if args.sensores < 1 or args.lecturas < 1 or not 0 <= args.duplicados <= 1:
        p.error("--sensores/--lecturas deben ser positivos y --duplicados debe estar entre 0 y 1.")

    umbral = leer_umbral_critico(args)
    ejecucion = uuid.uuid4().hex[:10]
    prefijo = f"stress_{ejecucion}"
    asegurar_sensores(args, args.sensores, prefijo)
    base = datetime.now(timezone.utc).replace(tzinfo=None)
    stats = dict(ok=0, alertas=0, duplicados=0, reintentos=0, errores=0)
    lock = threading.Lock()

    print(f"Ejecucion: {ejecucion}")
    print(f"Iniciando: {args.sensores} hilos x {args.lecturas} lecturas, "
          f"umbral critico PM2.5 = {umbral}")
    t0 = time.perf_counter()
    hilos = [threading.Thread(
        target=hilo_sensor, args=(args, i, prefijo, umbral, base, stats, lock)
    )
             for i in range(1, args.sensores + 1)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    dt = time.perf_counter() - t0

    print("\n--- Resultados ---")
    print(f"Lecturas guardadas:        {stats['ok']}")
    print(f"Alertas generadas:         {stats['alertas']}")
    print(f"Duplicados rechazados:     {stats['duplicados']}  (error 1062, esperado)")
    print(f"Reintentos por deadlock:   {stats['reintentos']}")
    print(f"Errores inesperados:       {stats['errores']}  (debe ser 0)")
    print(f"Tiempo total:              {dt:.2f} s")
    print(f"Rendimiento:               {stats['ok'] / dt:.0f} lecturas/s")
    integridad_ok = verificar(args, prefijo, stats["ok"], stats["alertas"])
    return 0 if stats["errores"] == 0 and integridad_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
