# Procedencia del conjunto de evaluación

- Repositorio: https://github.com/google-deepmind/miniF2F (fork de openai/miniF2F traducido a Lean 4)
- Commit usado: `f0a20e14c1eeccd859d51bb4c2b3ee487889c303`
- Archivo: `MiniF2F/Test.lean` (244 teoremas, copiado sin modificar a `data/raw/Test.lean`)
- Licencia: Apache 2.0 (ver `LICENSE`; el archivo original conserva su encabezado de copyright de OpenAI)
- Lean del dataset: v4.27.0. Lean de este proyecto: v4.36.0-rc2 (9 versiones menores más nuevo).
  => hay que comprobar que los enunciados compilan aquí: `python3 -m src.dataset check`
- Se descarta `Valid.lean`: 204 de sus teoremas usan `answer(...)`, que depende del paquete
  `formal_conjectures`, que no forma parte de este proyecto.
- El README del repositorio indica: docstrings en lenguaje natural para detectar mal-formalizaciones,
  "many fewer misformalizations" que el original y enunciados falsos conocidos eliminados.
  Aun así, la auditoría manual de una muestra sigue siendo necesaria.
- Referencia sobre errores del miniF2F original: arXiv:2511.03108 ("miniF2F-Lean Revisited").
