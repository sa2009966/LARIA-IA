# ADR-017: La nivelación es por rondas, y el nivel se guarda

- **Estado:** Aceptado
- **Fecha:** 2026-09-25
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Sustituye la forma de:** [ADR-016](ADR-016-diagnostico-de-entrada.md) (el diagnóstico existe; cambia cómo se administra)

## Contexto

El ADR-016 resolvió *que* el tutor puede evaluarte antes de enseñarte. Lo hacía con
**una** tanda de seis ítems mezclados (2 fáciles, 2 medios, 2 difíciles) y dejaba
como resultado mastery por concepto.

Eso mide el techo en una sola llamada al modelo, pero le faltan dos cosas que el
producto necesita:

1. **No da un veredicto.** Deja mastery repartido entre conceptos; no dice "este
   estudiante está en intermedio en ecuaciones". Y ese dato es el que decide por
   dónde empieza la ruta de aprendizaje.
2. **No se siente como una nivelación.** Seis preguntas sueltas de dificultad
   revuelta es un examen raro. Una ronda que se aprueba y da paso a otra más dura
   es una experiencia que el estudiante entiende sin que se la expliquen.

## Decisión

La nivelación se administra en **rondas sucesivas**, y el nivel alcanzado **se
persiste por tema**.

### 1. Dos rondas, tres veredictos

| Ronda | Qué prueba | Ítems | Reparto |
|---|---|---|---|
| 1 | lo básico del tema y su base | 6 | 4 fáciles + 2 medias |
| 2 | el dominio real del tema | 8 | 3 medias + 5 difíciles |

```
falla la ronda 1                    → básico
pasa la 1, falla la 2               → intermedio
pasa las dos                        → avanzado
```

Dos rondas y no cinco porque cada una cuesta una llamada al modelo y un rato del
estudiante. Con dos ya se distinguen los tres estados que cambian lo que el tutor
hace después; una tercera afinaría un matiz que la ruta de aprendizaje no usa.

### 2. Aprobar es 0,75

Hipótesis nombrada, como los cutoffs del ADR-004: no es una constante física. Se
elige alta a propósito — en una nivelación, un falso "avanzado" hace más daño que
un falso "intermedio", porque deja al estudiante con material por encima de su
nivel y sin que el sistema sepa por qué se atasca.

### 3. El nivel vive en el perfil, y lo escribe el projector

`StudentProfile.level_by_topic: dict[str, str]`. Lo escribe **el projector**, como
todo lo demás del perfil (invariante 1): el intento publica su evento, el projector
lee del quiz qué nivel se estaba probando y resuelve el veredicto.

El quiz gana `level`, que dice **qué ronda es**. Sin eso el projector no podría
distinguir un intento de nivelación de un quiz normal.

### 4. El backend sabe en qué ronda vas

`POST /quizzes/diagnostic` con `{"topic": "..."}` **no lleva la ronda**. El servicio
mira el nivel que ya tenga el estudiante en ese tema y genera la que toca. El
cliente no lleva estado: pide "evalúame en esto" y recibe lo que corresponda.

Quien ya está en `avanzado` y vuelve a pedirlo recibe otra vez la ronda avanzada:
revalidar es legítimo, y el mastery se actualiza con la evidencia nueva.

### 5. El nivel no sustituye al mastery, lo acompaña

Los ítems siguen dejando evidencia por concepto exactamente igual que antes. El
nivel es un **resumen para la ruta de aprendizaje**, no una fuente de verdad
paralela: si alguna vez discrepan, manda el mastery, que es lo que se mide de forma
continua. El nivel se recalcula en la siguiente nivelación.

## Consecuencias

- El cliente necesita saber, tras un intento, si hay otra ronda. La respuesta del
  intento gana `placement`, con el nivel alcanzado y si queda ronda siguiente.
- Una nivelación completa son **dos llamadas al modelo** en vez de una. Es el coste
  de tener veredicto; sigue siendo menos que los cinco turnos que hacían falta antes
  para que el motor empezara a adaptarse.
- El reparto del ADR-016 (2/2/2 mezclado) desaparece. Los tests que lo fijaban se
  reescriben: lo que protegían —que hay escalera y que lo fácil prueba la base— se
  mantiene dentro de cada ronda.

## Fuera de alcance

- **Preguntar al estudiante cómo prefiere aprender** (escuchando, viendo,
  dialogando). Va después de generar la ruta, es otra decisión y tiene una tensión
  propia: qué manda, lo que el estudiante dice o lo que se observa que le funciona.
  Ver ADR futuro.
- **Nivelación adaptativa por ítem** (tipo CAT). Ver ADR-016.
