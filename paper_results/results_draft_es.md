# Resultados — borrador en español (lenguaje sencillo)

Todas las cifras salen de los archivos de resultados del proyecto (`results/*.jsonl`). El texto en inglés está en `results_draft.tex`.

**Cómo leer las cifras.** Medimos qué proporción de problemas resuelve cada configuración, es decir, en cuántos entrega una prueba que Lean acepta (en el paper se llama *pass@1*). Cada configuración se probó una vez por problema. Los prompts y la forma de buscar lemas se fijaron con los 10 problemas de desarrollo, y los 20 de test se evaluaron una sola vez, con el código ya congelado.

## 1. Resultados generales
En los 20 problemas de test, todas las configuraciones resuelven muy pocos. La proporción va de 0.05 (Baseline A, 1 de 20) a 0.15 («sin RAG», 3 de 20). Con tan pocos problemas, el margen de incertidumbre es amplio y los márgenes de todas las configuraciones se superponen casi por completo. Por eso las comparaciones entre configuraciones no muestran diferencias claras: la mayor diferencia es de un solo problema, y ninguna es estadísticamente significativa. En los 10 problemas de desarrollo los resultados fueron mejores (hasta 0.60 en el sistema completo); esa diferencia se explica en la Discusión. *(Tablas 1 y 2, Fig. 1.)*

## 2. La verificación evita pruebas falsas
La línea base B no comprueba su trabajo: escribe la prueba y la da por buena. Por eso entregó los 20 problemas como correctos, pero Lean rechazó 18 de ellos (el 90 %). Las otras cuatro configuraciones solo entregan una prueba si Lean la acepta, y ninguna entregó una prueba incorrecta. En desarrollo pasó lo mismo: la línea base B entregó 10 pruebas y 6 eran falsas. *(Fig. 1b.)*

## 3. Qué problemas se resolvieron
Solo 3 problemas distintos de test fueron resueltos por alguna configuración:
- `aime_1989_p8`, resuelto por las cinco configuraciones;
- `mathd_algebra_441`, resuelto por todas menos Baseline A;
- `mathd_numbertheory_430`, resuelto únicamente por «sin RAG».

Ninguna configuración resolvió alguno de los 9 problemas de dificultad intermedia ni de los 7 de conteo. *(Fig. 2, Tabla 3.)*

## 4. Qué aportan el Crítico y el RAG
**El Crítico** revisa el error de Lean y pide corregir la prueba. En test, «sin RAG» resolvió 2 problemas a la primera y 1 después de un reintento (`mathd_numbertheory_430`). El sistema completo resolvió sus 2 problemas a la primera, aunque cambió de plan en 8 de los 20 problemas («sin RAG» lo hizo en 6). En desarrollo, los reintentos ayudaron más: rescataron 1 problema en «sin RAG» y 2 en el sistema completo (`mathd_numbertheory_99` y `mathd_numbertheory_521`).

**El RAG** busca lemas útiles de Mathlib y se los muestra al modelo. Ninguna de las 4 pruebas correctas de las configuraciones con RAG usa un lema buscado, así que no podemos atribuirle ningún acierto. *(Tabla 4.)*

## 5. Cuánto cuesta cada configuración
Las configuraciones con Crítico necesitan entre 9.6 y 10.2 consultas al modelo por problema, frente a 3.0 sin Crítico y entre 1.0 y 2.0 en las líneas base. También procesan mucho más texto: unos 9.8 mil a 11.7 mil tokens de entrada por problema, frente a 2.8 mil sin Crítico y entre 0.3 mil y 1.1 mil en las líneas base. Ese costo extra no se traduce en una proporción de aciertos claramente mejor que la de las configuraciones más baratas. *(Fig. 3.)*

## 6. Por qué fallan las pruebas
Clasificamos el último error de Lean en cada problema fallido. Los fallos se reparten entre varios tipos y ninguno desaparece al añadir componentes:
- instrucciones de Lean que no logran cerrar la meta (20 casos entre todas las configuraciones);
- uso de `sorry`, que deja la prueba incompleta (17 casos; entre 2 y 5 por configuración);
- nombres de lemas que no existen (16 casos; entre 2 y 4 por configuración);
- errores de escritura o de formalización (16 casos).

La clasificación se hace automáticamente a partir del mensaje de Lean, así que las cifras son aproximadas. *(Tabla 5, Fig. 4.)*
