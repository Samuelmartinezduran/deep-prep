// Estado compartido de la página. Es lo único mutable que se reparten los módulos: cada vista lee y
// escribe aquí, no en variables sueltas.
export const estado = {
  // Ventana encima del juego (?vista=overlay) en vez de la principal. Lo pone main.js al arrancar.
  overlay: false,
  // Pestaña abierta en la ventana principal: "partida", "revisiones" o "ajustes".
  vista: "partida",
  // Último /api/estado pintado, tal cual llegó: si no cambia, no se repinta.
  ultimo: "",
  // Último estado recibido, ya leído.
  actual: null,
  // Cuándo empezó la partida (ms) para el reloj; 0 = sin reloj.
  inicioPartida: 0,
  // Revisiones: la abierta (id), la última de la que ya se avisó y los datos de la lista (para el mapa de muertes).
  revisionVista: null,
  revisionAvisada: null,
  datosRevisiones: null,
  // Minuto del mapa del jungla rival y filtro del mapa de tus muertes.
  minutoMapa: "3",
  filtroMuertes: "todas",
  // Novedades de la versión ya cerradas en esta sesión.
  novedadesCerradas: false,
  // Campeones de los ajustes ({id, nombre}), como los manda /api/ajustes.
  campeones: [],
};
