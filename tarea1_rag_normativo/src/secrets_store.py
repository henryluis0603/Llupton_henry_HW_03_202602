"""Carga segura de la API key de OpenAI.

Orden de busqueda (el primero que encuentre gana):
  1. Variable de entorno OPENAI_API_KEY (ya sea exportada en la shell o
     cargada desde .env por python-dotenv).
  2. Llavero del sistema operativo (macOS Keychain / Windows Credential
     Locker / Secret Service en Linux), via la libreria `keyring`.

Por que el llavero es mas seguro que un .env: la key nunca queda en un
archivo de texto plano en disco -- queda cifrada por el sistema operativo
y ligada a la sesion del usuario. Se escribe con un prompt oculto (como
`sudo`), nunca visible en la terminal ni en el historial de comandos.

Para guardarla en el llavero (correr esto UNA VEZ, en tu propia terminal,
nunca compartiendo el valor):

    keyring set hw03_openai OPENAI_API_KEY

Eso abre un prompt oculto donde pegas la key. Este modulo la lee despues
automaticamente en cada corrida, sin que quede en ningun archivo del
repositorio.
"""
from __future__ import annotations

import os

SERVICE_NAME = "hw03_openai"
USERNAME = "OPENAI_API_KEY"


def get_openai_api_key() -> str | None:
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    try:
        import keyring

        return keyring.get_password(SERVICE_NAME, USERNAME)
    except Exception:
        return None
