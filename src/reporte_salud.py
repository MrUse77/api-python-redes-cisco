
import csv
import json
import sys
from datetime import datetime

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- Configuración -----------------------------------------------------------
BASE = "http://localhost:58000/api/v1"
USUARIO = "cisco"     # el que creaste en el dashboard
CLAVE = "class"
TIMEOUT = 15
SELLO = datetime.now().strftime("%Y%m%d_%H%M")


def get_token():
    r = requests.post(f"{BASE}/ticket",
                      json={"username": USUARIO, "password": CLAVE},
                      verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["response"]["serviceTicket"]


def get(ruta, token):
    r = requests.get(BASE + ruta, headers={"X-Auth-Token": token},
                     verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# Columnas de agregados: salen siempre, aun si una muestra no las trae.
COLUMNAS_FIJAS = (
    "timestamp",
    "clients_totalConnected",
    "clients_totalPercentage",
    "networkDevices_totalDevices",
    "networkDevices_totalPercentage",
)


def _texto(registro, clave):
    valor = registro.get(clave) if isinstance(registro, dict) else None
    return "" if valor is None else str(valor)


def _dispositivos(muestra):
    red = muestra.get("networkDevices")
    dispositivos = red.get("networkDevices") if isinstance(red, dict) else None
    if not isinstance(dispositivos, list):
        return []
    return [d for d in dispositivos if isinstance(d, dict)]


def muestras_de_salud(salud):
    if isinstance(salud, dict) and "response" in salud:
        salud = salud["response"]
    return [m for m in (salud if isinstance(salud, list) else [salud])
            if isinstance(m, dict)]


def columnas_de_salud(muestras):
    tipos = []
    for muestra in muestras:
        for dispositivo in _dispositivos(muestra):
            tipo = _texto(dispositivo, "deviceType")
            if tipo and tipo not in tipos:
                tipos.append(tipo)
    columnas = list(COLUMNAS_FIJAS)
    for tipo in tipos:
        columnas += [f"{tipo}_healthyPercentage", f"{tipo}_healthyRatio"]
    return columnas


def filas_de_salud(muestras):
    filas = []
    for muestra in muestras:
        clientes = muestra.get("clients") or {}
        red = muestra.get("networkDevices") or {}
        fila = {
            "timestamp": _texto(muestra, "timestamp"),
            "clients_totalConnected": _texto(clientes, "totalConnected"),
            "clients_totalPercentage": _texto(clientes, "totalPercentage"),
            "networkDevices_totalDevices": _texto(red, "totalDevices"),
            "networkDevices_totalPercentage": _texto(red, "totalPercentage"),
        }
        for dispositivo in _dispositivos(muestra):
            tipo = _texto(dispositivo, "deviceType")
            if not tipo:
                continue
            fila[f"{tipo}_healthyPercentage"] = _texto(dispositivo, "healthyPercentage")
            fila[f"{tipo}_healthyRatio"] = _texto(dispositivo, "healthyRatio")
        filas.append(fila)
    return filas


# Orden de lectura para un problema: cuándo, qué equipo, qué pasó.
CAMPOS_ISSUE_PREFERIDOS = ("issueTimestamp", "issueSource", "issueName",
                           "issueDescription", "issueId")


def _celda(valor):
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return str(valor)


def columnas_de_issues(issues):
    presentes = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        for clave in issue:
            if clave not in presentes:
                presentes.append(clave)
    preferidas = [c for c in CAMPOS_ISSUE_PREFERIDOS if c in presentes]
    return preferidas + [c for c in presentes if c not in preferidas]


def filas_de_issues(issues):
    columnas = columnas_de_issues(issues)
    return [{c: _celda(it.get(c)) for c in columnas}
            for it in issues if isinstance(it, dict)]


def issues_de_respuesta(crudo):
    """Los problemas vienen bajo `response`.

    Si el sobre no trae esa clave no hay problemas: el resto del sobre
    (`version`) es metadata y no un issue.
    """
    contenido = crudo.get("response", []) if isinstance(crudo, dict) else crudo
    if isinstance(contenido, dict):
        contenido = [contenido]
    if not isinstance(contenido, list):
        return []
    return [it for it in contenido if isinstance(it, dict)]


def escribir_csv(nombre, filas, campos):
    with open(nombre, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(f"  -> {nombre} ({len(filas)} filas)")


def main():
    token = get_token()
    print("Token obtenido.\n")

    # 1) Salud general de la red
    salud = get("/assurance/health", token)
    with open(f"salud_cruda_{SELLO}.json", "w", encoding="utf-8") as f:
        json.dump(salud, f, indent=2)
    muestras = muestras_de_salud(salud)
    filas_salud = filas_de_salud(muestras)
    print("Salud de la red:")
    if filas_salud:
        ultima = filas_salud[-1]
        print(f"  {len(filas_salud)} muestras, la última de {ultima['timestamp']}:"
              f" {ultima['clients_totalConnected']} clientes"
              f" ({ultima['clients_totalPercentage']}%),"
              f" {ultima['networkDevices_totalDevices']} equipos"
              f" ({ultima['networkDevices_totalPercentage']}% sano)")
    escribir_csv(f"salud_{SELLO}.csv", filas_salud, columnas_de_salud(muestras))

    # 2) Problemas detectados por Assurance
    crudo = get("/assurance/health-issues", token)
    with open(f"issues_crudos_{SELLO}.json", "w", encoding="utf-8") as f:
        json.dump(crudo, f, indent=2)

    issues = issues_de_respuesta(crudo)

    print(f"\nProblemas detectados: {len(issues)}")
    filas = filas_de_issues(issues)
    if filas:
        escribir_csv(f"issues_{SELLO}.csv", filas, columnas_de_issues(issues))
    else:
        print("  Sin problemas: la red no reporta issues.")

    # 3) Detalle de cada problema, si hay
    for it in issues:
        id_issue = it.get("id") or it.get("issueId")
        if not id_issue:
            continue
        try:
            det = get(f"/assurance/health/{id_issue}", token)
            print(f"  detalle {id_issue}: {json.dumps(det)[:200]}")
        except requests.HTTPError as e:
            print(f"  detalle {id_issue}: sin detalle ({e})")

    print("\nListo.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"Error HTTP: {e}", file=sys.stderr)
        sys.exit(1)
