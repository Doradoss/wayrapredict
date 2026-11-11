// Dirección del backend en producción (Azure App Service con el dominio propio api.wayrapredict.me).
// La usa `ng build` (configuración production); `npm start` sigue usando environment.ts (backend local en el puerto 8080).
// También responde en https://wayrapredict-api.azurewebsites.net (dirección por defecto de Azure).
export const environment = {
  apiUrl: 'https://api.wayrapredict.me',
};
