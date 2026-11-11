# Cómo encender WayraPredict (paso a paso)

La aplicación tiene tres partes y se encienden **en este orden**:

| Orden | Parte | Programa | Dirección |
|---|---|---|---|
| 1 | Base de datos (PostgreSQL) | Se enciende sola con Windows | `localhost:5432` |
| 2 | Backend (API, Spring Boot) | IntelliJ IDEA | http://localhost:8080 |
| 3 | Frontend (página web, Angular) | Visual Studio Code | http://localhost:4200 |

El orden importa: el frontend pide los datos al backend y el backend se los pide a la base de datos. Si el frontend se abre sin el backend encendido, la página carga pero muestra «No se pudo conectar con el servidor».

---

## Paso 1. Comprobar que la base de datos está encendida (30 segundos)

PostgreSQL se instala como un servicio de Windows y normalmente ya está encendido. Para comprobarlo:

1. Presiona **Win + R**, escribe `services.msc` y presiona Enter.
2. Busca **postgresql-x64-16** en la lista. También verás `postgresql-x64-18`: es otra instalación (puerto 5433) que WayraPredict no usa.
3. En la columna «Estado» debe decir **En ejecución**.
4. Si no lo dice, haz clic derecho sobre él y elige **Iniciar**.

Otra forma: abrir **pgAdmin** y entrar a la base `wayrapredict`. Si conecta, está encendida.

---

## Paso 2. Encender el backend en IntelliJ IDEA (1 minuto)

1. Abre **IntelliJ IDEA** con el proyecto `1-backend/wayrapredict-api`.
2. Arriba a la derecha, en el selector de configuraciones, debe aparecer **WayrapredictApiApplication**.
3. Presiona el botón verde **▶ Run** (o **Shift + F10**).
4. Abajo se abre la consola. Espera hasta ver estas dos líneas, que tardan unos 10 a 20 segundos:
   ```
   Tomcat started on port 8080 (http)
   Started WayrapredictApiApplication in ... seconds
   ```
5. **Déjalo encendido.** No cierres IntelliJ mientras uses la aplicación.

**Comprobación opcional:** abre http://localhost:8080/doc/swagger-ui/index.html en el navegador. Si aparece la documentación de la API (Swagger), el backend funciona.

**Si falla:** revisa `1-backend/PASOS_PGADMIN_Y_ARRANQUE.md`, sección «Problemas frecuentes». Los dos errores más comunes son:
- **Aparece `${WAYRA_API_DB_USER}` o similar en el error:** IntelliJ se abrió antes de definir las variables de entorno. Ciérralo por completo y vuelve a abrirlo.
- **`Port 8080 was already in use`:** el backend ya estaba encendido en otra ventana. Detén esa otra copia, o usa la que ya está funcionando.

---

## Paso 3. Encender el frontend en Visual Studio Code (1 minuto)

### 3.1 Abrir la carpeta correcta

1. Abre **Visual Studio Code**.
2. Menú **File → Open Folder…** (Archivo → Abrir carpeta…).
3. Elige la carpeta:
   ```
   PRUEBA_PROPHET-LSTM_OEFA\2-frontend\wayrapredict-web
   ```
   Tiene que ser `wayrapredict-web` (la que contiene `package.json`), no `2-frontend` ni la carpeta raíz.
4. Si VS Code pregunta «¿Confías en los autores de los archivos de esta carpeta?», elige **Sí, confío**.

### 3.2 Abrir la terminal de VS Code

1. Menú **Terminal → New Terminal** (Terminal → Nueva terminal), o presiona **Ctrl + ñ**. Si la ñ no funciona en tu teclado, usa **Ctrl + `**.
2. Abajo se abre un panel con algo como:
   ```
   PS C:\Users\danie\Downloads\PRUEBA_PROPHET-LSTM_OEFA\2-frontend\wayrapredict-web>
   ```
   Comprueba que la ruta termine en `wayrapredict-web`. Si no, escribe esto y presiona Enter:
   ```powershell
   cd C:\Users\danie\Downloads\PRUEBA_PROPHET-LSTM_OEFA\2-frontend\wayrapredict-web
   ```

### 3.3 Solo la primera vez: instalar las dependencias

Si la carpeta `node_modules` no existe (por ejemplo, en otra computadora o después de borrarla), escribe:
```powershell
npm install
```
Tarda de 1 a 3 minutos. En tu computadora actual **ya está hecho**, así que puedes saltar este paso.

### 3.4 Encender el frontend

En la terminal escribe y presiona Enter:
```powershell
npm start
```

**Qué vas a ver:**
- Si pregunta *«Would you like to share pseudonymous usage data…?»* o *«…enable autocompletion?»*, escribe **N** y presiona Enter. Si se queda esperando sin hacer nada, probablemente esté esperando esa respuesta.
- Al cabo de unos segundos aparece:
  ```
  ➜  Local:   http://localhost:4200/
  ➜  press h + enter to show help
  ```

### 3.5 Abrir la aplicación

1. Mantén presionada la tecla **Ctrl** y haz clic en `http://localhost:4200/` dentro de la terminal, o escribe esa dirección en el navegador.
2. Aparece la pantalla **Iniciar sesión**. Desde ahí puedes:
   - **Consultar sin cuenta:** el acceso ciudadano.
   - **Ingresar** con tu cuenta de administrador.

**Déjalo encendido.** Mientras la terminal esté abierta, la página se actualiza sola cuando se cambia el código.

---

## Cómo apagar todo

| Parte | Cómo apagarla |
|---|---|
| Frontend | En la terminal de VS Code presiona **Ctrl + C**. Si pregunta *¿Desea terminar el trabajo por lotes (S/N)?*, escribe **S** y Enter. También puedes cerrar VS Code |
| Backend | En IntelliJ presiona el botón rojo **■ Stop** (o **Ctrl + F2**) |
| Base de datos | No hace falta apagarla: sigue como servicio de Windows sin molestar |

---

## Problemas frecuentes del frontend

| Lo que ves | Qué significa | Qué hacer |
|---|---|---|
| `npm : El término 'npm' no se reconoce…` | VS Code no encuentra Node.js | Cierra VS Code y ábrelo de nuevo. Si sigue, instala Node.js LTS desde https://nodejs.org y reinicia la computadora |
| `Port 4200 is already in use` | Ya hay otro frontend encendido | Ciérralo con Ctrl + C en su terminal. O responde **Y** cuando pregunte si quieres usar otro puerto, y abre la dirección que indique |
| La terminal se queda quieta tras `npm start` | Está esperando una respuesta (ver 3.4) | Escribe **N** y Enter. Si no avanza, Ctrl + C y repite `npm start` |
| La página dice «No se pudo conectar con el servidor» | El backend está apagado | Haz el paso 2 y recarga la página (**F5**) |
| La página se ve antigua (logo o colores viejos) | El navegador guardó la versión anterior | Recarga con **Ctrl + F5** |
| `Cannot find module…` o errores al iniciar | Faltan dependencias | Ejecuta `npm install` y luego `npm start` |
| «Correo o contraseña incorrectos» con tu cuenta | La contraseña no coincide | Revisa mayúsculas. Si la olvidaste, ver `1-backend/PASOS_PGADMIN_Y_ARRANQUE.md`, «Si olvidas tu contraseña de administrador» |

---

## Resumen rápido (cuando ya lo hayas hecho una vez)

1. **IntelliJ:** abrir `1-backend/wayrapredict-api` → **▶ Run** → esperar `Started WayrapredictApiApplication`.
2. **VS Code:** abrir `2-frontend/wayrapredict-web` → **Terminal → New Terminal** → `npm start`.
3. **Navegador:** http://localhost:4200

**Direcciones útiles:**
- Aplicación: http://localhost:4200
- Documentación de la API (Swagger): http://localhost:8080/doc/swagger-ui/index.html
- Base de datos: pgAdmin → servidor PostgreSQL 16 → base `wayrapredict`
