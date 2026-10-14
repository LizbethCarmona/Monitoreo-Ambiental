"""Conexion a MySQL para la API (monitoreo_ambiental).

Usa las mismas variables de entorno que src/database/carga_concurrente.py y
src/cpp_ingestion (MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
MYSQL_DATABASE), para que los tres componentes apunten siempre a la misma
base de datos sin duplicar configuracion.
"""
import os

import mysql.connector


def conectar():
    password = os.getenv("MYSQL_PASSWORD")
    if password is None:
        raise RuntimeError(
            "Falta la variable de entorno MYSQL_PASSWORD. En PowerShell: "
            "$env:MYSQL_PASSWORD = 'tu_clave'"
        )
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=password,
        database=os.getenv("MYSQL_DATABASE", "monitoreo_ambiental"),
        # use_pure=True evita la extension en C de mysql-connector-python,
        # que no es segura para usarse desde varios hilos del pool de
        # workers de uvicorn al mismo tiempo (se observo un crash nativo
        # access-violation en Windows al recibir requests concurrentes).
        use_pure=True,
    )
