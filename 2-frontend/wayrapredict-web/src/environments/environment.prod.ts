// Dirección del backend en producción (Azure App Service). La usa `ng build` (configuración production);
// `npm start` sigue usando environment.ts (backend local en el puerto 8080).
// Cuando el dominio propio esté configurado, puede cambiarse a 'https://api.wayrapredict.me'.
export const environment = {
  apiUrl: 'https://wayrapredict-api.azurewebsites.net',
};
