import os

import flet as ft

from main import main

if __name__ == "__main__":
    # Configuração de porta e host para execução web
    port = int(os.environ.get("PORT", "8550"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Iniciando Hinário Inteligente Web em http://{host}:{port} ...")
    ft.run(
        main,
        view=ft.AppView.WEB_BROWSER,
        assets_dir="assets",
        host=host,
        port=port,
    )
