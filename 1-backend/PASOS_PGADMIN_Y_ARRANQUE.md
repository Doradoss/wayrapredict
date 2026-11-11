# Cómo dejar listo el backend: pasos simples

| Paso | Qué es | Estado |
|---|---|---|
| 1 | Crear en pgAdmin el usuario `wayra_api`, la "llave" del backend | ✅ **Hecho** (comprobado: `wayra_api` existe y tiene sus 11 permisos) |
| 2 | Decirle a Windows las contraseñas del backend (PowerShell, `setx`) | ⏳ Pendiente |
| 3 | Arrancar el backend | ⏳ Pendiente |
| — | Tu cuenta de administrador de la plataforma | ✅ **Creada** el 04/11/2026: `tu_correo_de_administrador@dominio.com`, rol administrador, aprobada. La contraseña es la que elegiste |

## Hay dos "usuarios" distintos

- **`wayra_api`** (paso 1): es el usuario de **PostgreSQL** con el que el backend se conecta a la base. Ninguna persona inicia sesión en la web con él.
- **Tu cuenta `tu_correo_de_administrador@dominio.com`**: es un usuario de la **plataforma**. Con ella entras al login (Swagger y luego el frontend) y apruebas a las autoridades. Ya está creada.

## Paso 1. Crear `wayra_api` en pgAdmin (ya lo hiciste)

Solo para referencia:
1. Abres el Query Tool en la base **wayrapredict**.
2. Pegas el contenido de `sql/crear_usuario_wayra_api.sql`, después de cambiar las dos apariciones de `CAMBIAR_ESTA_CONTRASENA` por tu contraseña.
3. Presionas F5.

**Necesitas esa misma contraseña en el paso 2.** Si no la recuerdas, repite el paso 1 con una nueva: el script la actualiza.

## Paso 2. Decirle a Windows las contraseñas (PowerShell)

### ¿Hace falta moverse a alguna carpeta?

**No.** `setx` guarda valores en **Windows**, no en una carpeta ni en la base de datos. Funciona igual desde cualquier carpeta en la que esté abierto PowerShell. Lo que hace es dejar anotado en tu usuario de Windows, por ejemplo, «la contraseña del backend es tal». Después, cuando arranca, el backend lee esas anotaciones y con ellas se conecta a la base. PowerShell no se conecta a nada en este paso: solo guarda los valores.

### Cómo hacerlo

1. Abre **PowerShell**: tecla Windows, escribe `PowerShell` y presiona Enter. No necesita ser como administrador.
2. Pega estas líneas **una por una**, presionando Enter después de cada una. Cambia lo que está entre comillas:

```
setx WAYRA_API_DB_USER "wayra_api"
setx WAYRA_API_DB_PASSWORD "la_contraseña_que_pusiste_en_pgadmin_para_wayra_api"
setx WAYRA_JWT_SECRET "pega_aqui_la_clave_larga_del_punto_3"
setx WAYRA_ADMIN_CORREO "tu_correo_de_administrador@dominio.com"
setx WAYRA_ADMIN_PASSWORD "tu_contraseña_de_administrador"
```

   Cada línea debe responder `CORRECTO: se guardó el valor especificado.` (o `SUCCESS` si tu Windows está en inglés).

3. **La clave del token (`WAYRA_JWT_SECRET`)** es un texto largo al azar con el que el backend firma los inicios de sesión. Para generarla, pega esto en PowerShell y presiona Enter:
   ```
   [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Maximum 256 }))
   ```
   Copia el texto que aparece, de unos 88 caracteres, y úsalo en la línea `setx WAYRA_JWT_SECRET "..."`.

4. **`WAYRA_ADMIN_CORREO` y `WAYRA_ADMIN_PASSWORD`:** tu administrador ya existe, así que el backend no creará otro. Igual conviene definirlas: si algún día borras tu usuario, el backend lo vuelve a crear con esos datos al arrancar.

5. **Cierra PowerShell y ábrelo de nuevo.** Si usas IntelliJ, ciérralo y ábrelo también. Los valores de `setx` solo se ven en ventanas abiertas después de guardarlos.

6. **Comprueba** en la ventana nueva. Debe mostrar `wayra_api`:
   ```
   echo $env:WAYRA_API_DB_USER
   ```
   No imprimas las contraseñas en pantalla para evitar que queden en una captura.

## Paso 3. Arrancar el backend

**Opción A: IntelliJ (recomendada).** Abre la carpeta `1-backend\wayrapredict-api` como proyecto y ejecuta la clase `WayrapredictApiApplication` (botón ▶).

**Opción B: PowerShell.** Aquí **sí** hay que ir a la carpeta del proyecto, porque el comando `mvnw` está dentro de ella:
```
cd "C:\Users\danie\Downloads\PRUEBA_PROPHET-LSTM_OEFA\1-backend\wayrapredict-api"
.\mvnw.cmd spring-boot:run
```

**Cómo saber que arrancó bien:**
- Al final del log aparecen `Tomcat started on port 8080` y `Started WayrapredictApiApplication`.
- Si dice `password authentication failed for user "wayra_api"`, la contraseña del paso 2 no es la misma del paso 1. Corrígela con `setx` y vuelve a abrir la ventana.
- **Para detenerlo:** Ctrl + C en PowerShell, o el botón ■ en IntelliJ.

## Paso 4. Probar con tu cuenta en Swagger

1. Abre http://localhost:8080/doc/swagger-ui/index.html.
2. **Inicia sesión:**
   1. Busca `POST /authenticate` y haz clic en **Try it out**.
   2. Escribe:
      ```json
      { "correo": "tu_correo_de_administrador@dominio.com", "password": "tu_contraseña" }
      ```
   3. Haz clic en **Execute** y copia el valor de `jwttoken` de la respuesta.
3. **Autorízate:** clic en **Authorize** (candado, arriba a la derecha), pega el token, luego **Authorize** y **Close**.

**Para probar la aprobación de una autoridad:**
1. **Solicita la cuenta.** En `POST /api/libre/solicitar-cuenta`, haz clic en **Try it out**. No necesita token. Escribe:
   ```json
   { "nombres": "Luis", "apellidos": "Mamani", "correo": "prueba@oefa.gob.pe", "password": "Prueba2026!",
     "institucion": "OEFA", "cargo": "Especialista ambiental", "aceptaTratamientoDatos": true }
   ```
   Respuesta: **201**, con estado `pendiente`.
2. **Comprueba que no puede entrar.** En `POST /authenticate`, inicia sesión con esa cuenta. Respuesta: **403**, «pendiente de aprobación».
3. **Busca la solicitud.** En `GET /api/admin/usuarios`, con tu token y `estado = pendiente`, verás la solicitud con su `idUsuario`.
4. **Apruébala.** En `PUT /api/admin/aprobar-usuario/{id}`, escribe ese `id`. Respuesta: **200**, con estado `aprobado` y `aprobadoPor` igual a tu correo.
5. **Entra como la autoridad.** Ahora esa cuenta sí inicia sesión, y con su token puede usar `PUT /api/institucional/verificar-prediccion/{id}`.

Este mismo flujo ya lo probé con tu cuenta. Las capturas están en `evidencias/imagenes/Flujo1` a `Flujo6`. La autoridad de prueba se borró al terminar, para que la pruebes tú desde cero.

## Si olvidas tu contraseña de administrador

En pgAdmin, Query Tool:
```sql
DELETE FROM usuario WHERE correo = 'tu_correo_de_administrador@dominio.com';
```
Después pon la nueva contraseña con `setx WAYRA_ADMIN_PASSWORD "..."`, vuelve a abrir la ventana y arranca el backend: crea tu administrador de nuevo.

Si ya aprobaste cuentas con ese administrador, el `DELETE` puede fallar porque esas cuentas lo tienen registrado en `aprobado_por`. En ese caso, pídeme que lo resuelva.

## Sobre las contraseñas

- No las guardes en archivos dentro del proyecto. `setx` las guarda en Windows, fuera del proyecto.
- **Al desplegar** (Azure u otro servicio), las variables se configuran en el panel del servicio, con otra contraseña de base de datos.

## Problemas frecuentes

**El error dice `la autentificación password falló para el usuario «${WAYRA_API_DB_USER}»`, o aparece `${...}` en vez de un valor.**
El programa no ve las variables de entorno: se abrió **antes** de los `setx`. Un programa solo conoce las variables que existían cuando se abrió.
1. Cierra IntelliJ **por completo**: menú *File → Exit*, no solo la ventana del proyecto.
2. Abre el Administrador de tareas (Ctrl + Shift + Esc) y comprueba que no quede ningún proceso `IntelliJ IDEA` o `idea64`. Si queda, finalízalo.
3. Vuelve a abrir IntelliJ desde el menú Inicio y ejecuta `WayrapredictApiApplication`.
4. Si lo abres con JetBrains Toolbox, cierra también Toolbox (icono junto al reloj → *Quit*) y vuelve a abrirlo.
5. Si aun así no funciona, cierra sesión en Windows y vuelve a entrar, o reinicia la PC.

No pongas las contraseñas en *Run/Debug Configurations → Environment variables* de IntelliJ: se guardan en la carpeta `.idea` del proyecto y podrían subirse por error.

**El error dice `password authentication failed for user "wayra_api"`.**
La contraseña de `setx WAYRA_API_DB_PASSWORD` no es la misma que pusiste en pgAdmin. Repite el paso 1 o el `setx` con la misma contraseña, y vuelve a abrir IntelliJ.
