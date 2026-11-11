package com.wayrapredict.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.test.context.SpringBootTest;

//Arranca el contexto completo contra la base real (valida el mapeo con ddl-auto=validate).
//Solo corre si están definidas las variables de conexión del backend.
@SpringBootTest
@EnabledIfEnvironmentVariable(named = "WAYRA_API_DB_USER", matches = ".+")
class WayrapredictApiApplicationTests {

	@Test
	void contextLoads() {
	}

}
