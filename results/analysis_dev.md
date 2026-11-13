# Resultados — conjunto `dev` (n = 10)

## 1. pass@1 y costo

| Configuración | pass@1 [Wilson 95 %] | Entregadas como correctas | Falsos positivos | Llamadas/problema | Tokens in / out por problema | Latencia (s) |
|---|---|---|---|---|---|---|
| Baseline A | 4/10 = 0.40 [0.17, 0.69] | 4 | 0 | 1.0 | 232 / 1110 | 8 |
| Baseline B | 4/10 = 0.40 [0.17, 0.69] | 10 | 6 | 2.0 | 980 / 2036 | 16 |
| Sin RAG | 5/10 = 0.50 [0.24, 0.76] | 5 | 0 | 8.0 | 7599 / 3315 | 31 |
| Sin Crítico | 4/10 = 0.40 [0.17, 0.69] | 4 | 0 | 3.0 | 2605 / 1182 | 2 |
| Completo | 6/10 = 0.60 [0.31, 0.83] | 6 | 0 | 7.9 | 9259 / 3248 | 79 |

Falso positivo = prueba entregada como correcta que Lean rechaza. La línea base B no verifica dentro del sistema (la verificación es solo medición), por eso allí aparecen; en las demás configuraciones el veredicto de Lean decide, así que son 0.

## 2. pass@1 por área

| área | Baseline A | Baseline B | Sin RAG | Sin Crítico | Completo |
|---|---|---|---|---|---|
| algebra | 2/5 | 3/5 | 3/5 | 3/5 | 3/5 |
| conteo | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| teoria_de_numeros | 1/3 | 0/3 | 1/3 | 0/3 | 2/3 |

## 2. pass@1 por dificultad

| dificultad | Baseline A | Baseline B | Sin RAG | Sin Crítico | Completo |
|---|---|---|---|---|---|
| avanzado | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| basico | 4/6 | 4/6 | 5/6 | 4/6 | 6/6 |
| intermedio | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |

## 3. Comparaciones pareadas

| Comparación | n | solo 1.º acierta | solo 2.º acierta | Δ pass@1 [bootstrap 95 %] | p (McNemar exacto) | p Bonferroni (×5) |
|---|---|---|---|---|---|---|
| Completo vs Sin RAG | 10 | 1 | 0 | +0.10 [+0.00, +0.30] | 1.000 | 1.000 |
| Completo vs Sin Crítico | 10 | 2 | 0 | +0.20 [+0.00, +0.50] | 0.500 | 1.000 |
| Completo vs Baseline A | 10 | 2 | 0 | +0.20 [+0.00, +0.50] | 0.500 | 1.000 |
| Completo vs Baseline B | 10 | 2 | 0 | +0.20 [+0.00, +0.50] | 0.500 | 1.000 |
| Sin Crítico vs Baseline A | 10 | 1 | 1 | +0.00 [-0.30, +0.30] | 1.000 | 1.000 |

Con n pequeño solo diferencias grandes pueden ser significativas; se reporta igualmente el tamaño de la diferencia con su intervalo.

## 4. Contribución del Crítico y del RAG

| Configuración | Resueltos al primer intento (3 llamadas) | Resueltos tras reintento o replan (>3 llamadas) | Problemas con replanificación | Pruebas verificadas que usan un lema recuperado |
|---|---|---|---|---|
| Sin RAG | 4 | 1 | 3 | — |
| Sin Crítico | 4 | 0 | 0 | 0/4 |
| Completo | 4 | 2 | 3 | 0/6 |

El pass@1 no distingue si el RAG intervino: esta última columna cuenta las pruebas correctas cuyo texto contiene algún lema recuperado.

## 5. Taxonomía de errores (intentos fallidos)

| Categoría | Baseline A | Baseline B | Sin RAG | Sin Crítico | Completo |
|---|---|---|---|---|---|
| táctica no cierra la meta | 4 | 3 | 3 | 2 | 2 |
| alucinación de identificador | 2 | 0 | 1 | 1 | 1 |
| tipos / instancias | 0 | 3 | 0 | 0 | 0 |
| uso de sorry/admit | 0 | 0 | 1 | 1 | 0 |
| sintaxis / formalización | 0 | 0 | 0 | 2 | 1 |

Clasificación heurística por el mensaje de Lean del último intento; conviene revisar a mano los casos `otro` y los ambiguos antes de citar cifras.

## 6. Por problema

| problema | área | dificultad | Baseline A | Baseline B | Sin RAG | Sin Crítico | Completo |
|---|---|---|---|---|---|---|---|
| amc12_2000_p20 | algebra | intermedio | ✗ | ✗ | ✗ | ✗ | ✗ |
| amc12a_2021_p19 | conteo | intermedio | ✗ | ✗ | ✗ | ✗ | ✗ |
| imo_1962_p2 | algebra | avanzado | ✗ | ✗ | ✗ | ✗ | ✗ |
| imo_1974_p3 | teoria_de_numeros | avanzado | ✗ | ✗ | ✗ | ✗ | ✗ |
| mathd_algebra_141 | algebra | basico | ✓ | ✓ | ✓ | ✓ | ✓ |
| mathd_algebra_33 | algebra | basico | ✗ | ✓ | ✓ | ✓ | ✓ |
| mathd_algebra_398 | algebra | basico | ✓ | ✓ | ✓ | ✓ | ✓ |
| mathd_numbertheory_12 | conteo | basico | ✓ | ✓ | ✓ | ✓ | ✓ |
| mathd_numbertheory_521 | teoria_de_numeros | basico | ✗ | ✗ | ✗ | ✗ | ✓ |
| mathd_numbertheory_99 | teoria_de_numeros | basico | ✓ | ✗ | ✓ | ✗ | ✓ |
