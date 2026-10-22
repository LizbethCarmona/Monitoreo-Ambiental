import os
import unittest
from unittest.mock import patch

from carga_concurrente import crear_parser


class PruebasConfiguracionCarga(unittest.TestCase):
    def test_opciones_mysql_usan_variables_de_entorno(self):
        configuracion = {
            "MYSQL_HOST": "db.local",
            "MYSQL_PORT": "3307",
            "MYSQL_USER": "monitoreo_app",
            "MYSQL_DATABASE": "monitoreo_pruebas",
        }
        with patch.dict(os.environ, configuracion, clear=True):
            args = crear_parser().parse_args([])

        self.assertEqual(args.host, "db.local")
        self.assertEqual(args.puerto, 3307)
        self.assertEqual(args.usuario, "monitoreo_app")
        self.assertEqual(args.base, "monitoreo_pruebas")


if __name__ == "__main__":
    unittest.main()
