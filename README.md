# API del Network Controller (Cisco Packet Tracer) en Python

Cliente mínimo en Python contra la API REST del Network Controller de Packet
Tracer (`http://localhost:58000/api/v1`): obtención del ticket de sesión,
consultas de dispositivos y hosts, salida en tablas y un reporte de salud de la
red.

## Estructura del repositorio

```
src/                    scripts
requirements.txt        dependencias (requests, tabulate, ...)
salud_*.csv             reporte de salud (lo genera reporte_salud.py)
issues_*.csv            problemas detectados (lo genera reporte_salud.py)
*_crudos_*.json         respuestas crudas del controlador
```

## Instalación en Linux

### 1. Clonación del proyecto

Desde la terminal ejecutar:

**git clone** `<URL_del_repositorio>` `<nombre_de_la_carpeta_de_destino>`

Luego ejecutar **cd** `<nombre_de_la_carpeta_de_destino>`. Esta carpeta será la
raíz de nuestro proyecto en Python.

### 2. Creación del entorno virtual

Supongamos que el nombre que le damos al entorno virtual es **cisco**, entonces
se creará una carpeta **cisco** con todas las librerías y dependencias
necesarias para nuestro proyecto.

La manera de realizarlo es la siguiente:

```
python3 -m venv <nombre_del_entorno>
```

Ejemplo: `python3 -m venv cisco`

Para activar el entorno escribimos **source cisco/bin/activate**, en la carpeta
raíz del proyecto. El nombre del entorno virtual aparecerá entre paréntesis ().

### 3. Instalación de las dependencias

En la carpeta raíz de nuestro proyecto y dentro del entorno virtual escribimos:
**pip install -r requirements.txt**

### 4. Selección del intérprete Python para nuestro entorno virtual

<img width="881" height="118" alt="image" src="https://github.com/user-attachments/assets/18c41d8e-d338-48b6-953c-b2499c57319f" />

<img width="736" height="412" alt="image" src="https://github.com/user-attachments/assets/2a795fcd-2cf8-47ef-a5a6-d21e09ce967f" />

Tal como se ve en la figura seleccionamos Python 3.10.12 (cisco) que se mostrará
como entorno recomendado.

### 5. Desactivación del entorno virtual

Simplemente escribimos en la línea de comandos: **deactivate**

## Qué hace cada script

Todos apuntan al controlador en `http://localhost:58000/api/v1` y se ejecutan
desde la carpeta `src/` (o con la ruta completa). La autenticación es en dos
pasos: primero se pide un **ticket** (`serviceTicket`) con usuario y clave, y
después ese ticket viaja en el header `X-Auth-Token` de cada consulta.

### `01_get-ticket.py` — obtener el ticket de sesión

Hace un `POST /api/v1/ticket` con las credenciales (usuario `cisco`, clave
`class`) en formato JSON. Muestra:

1. el código de estado HTTP de la solicitud,
2. la respuesta JSON completa del controlador,
3. el ticket en texto plano (`response.serviceTicket`).

Ese ticket es el que necesitan los demás scripts. El controlador lo genera de
nuevo en cada sesión y vence, así que hay que volver a pedirlo cuando las
consultas empiezan a fallar.

### `02_get-network-device.py` — listar dispositivos de red

Hace un `GET /api/v1/network-device` con el ticket en el header
`X-Auth-Token`. Imprime el estado de la solicitud, la respuesta JSON completa y,
al final, una línea por dispositivo con **hostname**, **platformId** y
**managementIpAddress** separados por tabulaciones.

### `03_get-host.py` — listar equipos con MAC e interfaz

Hace un `GET /api/v1/network-device` con el ticket en el header `X-Auth-Token`
(el pedido va con `verify=False`, es decir sin validar el certificado TLS).
Imprime el estado, la respuesta JSON completa y, al final, una línea por equipo
con **hostname**, **managementIpAddress**, **macAddress** y
**connectedInterfaceName**.

### `04_tabulate.py` — reporte en tablas

Es el script autónomo del conjunto: pide el ticket por su cuenta (no hay que
copiar nada a mano) y con ese único ticket arma tres consultas:

1. `POST /ticket` — muestra el estado y el ticket obtenido.
2. `GET /network-device` — tabla con **Hostname**, **Serial Number** y
   **Software Version** de cada dispositivo.
3. `GET /host` — tabla con **Hostname**, **Tipo** y **IP** de cada host.

Las tablas se imprimen con `tabulate` en formato `rst`.

### `reporte_salud.py` — salud de la red y problemas detectados

Reporte de *Assurance*. Pide el ticket y después consulta
`/assurance/health` y `/assurance/health-issues`, con `timeout` de 15 segundos y
sin validar el certificado TLS. Escribe los archivos en el directorio desde
donde se ejecuta, con un sello de fecha y hora local (`AAAAMMDD_HHMM`):

| Archivo | Contenido |
| --- | --- |
| `salud_cruda_<sello>.json` | respuesta cruda de `/assurance/health` |
| `salud_<sello>.csv` | una fila por muestra de salud |
| `issues_crudos_<sello>.json` | respuesta cruda de `/assurance/health-issues` |
| `issues_<sello>.csv` | una fila por problema detectado |

Detalles del reporte:

- **Salud:** el CSV trae siempre las columnas `timestamp`,
  `clients_totalConnected`, `clients_totalPercentage`,
  `networkDevices_totalDevices` y `networkDevices_totalPercentage`, más dos
  columnas por cada tipo de equipo que informe el controlador
  (`<tipo>_healthyPercentage` y `<tipo>_healthyRatio`, por ejemplo
  `Switches_healthyPercentage`). La tabla se adapta a los tipos presentes. Por
  pantalla muestra cuántas muestras hay y el resumen de la última: clientes
  conectados y equipos sanos.
- **Problemas:** los issues se leen de `response`. Si el sobre no trae issues,
  informa `Problemas detectados: 0` y **no** escribe el CSV. Si hay problemas,
  el CSV ordena primero las columnas `issueTimestamp`, `issueSource`,
  `issueName`, `issueDescription` e `issueId` y después agrega el resto de los
  campos que vengan (los valores anidados se guardan como JSON).
- **Detalle por problema:** para cada issue con identificador consulta
  `/assurance/health/<id>` y muestra un extracto del detalle; si el controlador
  no lo devuelve, avisa "sin detalle" y sigue con el siguiente.
- Si una consulta falla a nivel HTTP, imprime `Error HTTP: ...` en stderr y
  termina con código 1.

### `test_reporte_salud.py` — chequeos de `reporte_salud.py`

Suite de `unittest` que corre sin red y sin controlador: reemplaza las llamadas
HTTP por dobles de prueba y ejecuta `main()` dentro de un directorio temporal.
Verifica que lo que se informa por pantalla coincida con lo que se escribe en
disco: un sobre sin problemas no inventa issues ni genera CSV, y un issue real
se informa y queda en el CSV. Se ejecuta desde `src/`:

```
python3 -m unittest test_reporte_salud -v
```

## Cambios respecto de la versión anterior

### `01_get-ticket.py`

- Se actualizó la clave del cuerpo de autenticación a `class`, la del usuario
  `cisco` del controlador.

### `02_get-network-device.py`

- Se actualizó el ticket escrito en el header `X-Auth-Token` al de la última
  sesión. Sigue siendo un valor fijo en el código: hay que reemplazarlo por el
  ticket que devuelve `01_get-ticket.py`, porque el controlador lo renueva y
  vence.

### `03_get-host.py`

- La consulta pasó de `/api/v1/host` a `/api/v1/network-device`, así que el
  script ahora lista dispositivos de red y ya no hosts.
- En consecuencia, los campos impresos pasaron de los de host a los de
  dispositivo: `hostname`, `managementIpAddress` y `macAddress`, y se mantiene
  `connectedInterfaceName`.
- Se actualizó el ticket escrito en el header `X-Auth-Token` al de la última
  sesión, con la misma advertencia que en `02`: es un valor fijo que hay que
  reemplazar por el de `01_get-ticket.py`.

### `04_tabulate.py`

- Se actualizó la clave usada para pedir el ticket a `class`, la del usuario
  `cisco` del controlador.

## Antes de ejecutar los scripts

- **Credenciales del controlador:** los scripts usan el usuario `cisco` y la
  clave `class`. Si en tu Network Controller creaste otro usuario, cambialos en
  `01_get-ticket.py` y en `04_tabulate.py` (y en `reporte_salud.py`, donde
  están como `USUARIO` y `CLAVE`).
- **Ticket (X-Auth-Token):** `02_get-network-device.py` y `03_get-host.py`
  traen escrito un ticket de ejemplo que **no va a funcionar** en tu Packet
  Tracer, porque el controlador genera uno nuevo en cada sesión y vence.
  Ejecutá primero `01_get-ticket.py`, copiá el ticket que muestra y reemplazalo
  en el header `X-Auth-Token` de esos dos scripts. `04_tabulate.py` y
  `reporte_salud.py` no necesitan este paso: piden el ticket solos.

## Orden de ejecución sugerido

```
cd src
python3 01_get-ticket.py          # obtener el ticket de la sesión
python3 02_get-network-device.py  # dispositivos de red
python3 03_get-host.py            # equipos con MAC e interfaz
python3 04_tabulate.py            # tablas de dispositivos y hosts
python3 reporte_salud.py          # salud de la red + CSV
python3 -m unittest test_reporte_salud -v   # chequeos del reporte
```
