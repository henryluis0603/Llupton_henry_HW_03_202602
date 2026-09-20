# Tarea 2 — Fase 5: Indicador de riesgo (postor único)

## Metodología

Script: `src/risk_indicator.py`. Un proceso cuenta como **adjudicado** si su `ocid` aparece en
`com_awards.csv` de su mes; es de **postor único** si
`compiledRelease/tender/numberOfTenderers == 1` (un solo proveedor presentó oferta). Se calcula
el % de adjudicaciones de postor único por departamento y por comprador (`buyer_name`, con un
mínimo de 5 procesos adjudicados para entrar al ranking, para no destacar compradores con muestras
demasiado chicas como si fueran comparables a uno con cientos de procesos).

## Resultado real (3 meses, 2026-06 a 2026-08)

- **13,742** procesos adjudicados con dato de número de postores disponible.
- **Tasa global de postor único: 13.1%**.
- Departamentos con mayor tasa: **Tumbes (36.7%, 120 adjudicaciones)** y **Lima (30.2%, 3,862
  adjudicaciones)** — Lima destaca porque, aunque su tasa no es la más alta, es la que más
  concentra en términos absolutos (1,165 adjudicaciones de postor único).
- Top comprador individual: **"FOMENTO Y GESTIÓN SOSTENIBLE DE LA PRODUCCIÓN FORESTAL EN EL
  PERÚ"** y otros 3 compradores con **100% de postor único** (aunque con volúmenes bajos, 6-22
  procesos) — el caso más relevante por volumen es el **Organismo de Evaluación y Fiscalización
  Ambiental (OEFA)**, con **174 adjudicaciones y 95.4% de postor único**.

## Advertencia (tal como exige el enunciado)

Este indicador **señala necesidad de investigación, no prueba irregularidad**. Una tasa alta de
postor único puede explicarse por mercados de proveedores pequeños (bienes/servicios altamente
especializados, como en el caso de OEFA que probablemente contrata servicios técnicos muy
específicos) y no necesariamente por coordinación indebida entre postores o direccionamiento.
Esta advertencia se muestra también en el dashboard (Fase 4), no solo en este documento.

## Limitación declarada

- El "número de postores" viene del campo `tender/numberOfTenderers` de OCDS, que mide cuántos
  proveedores **presentaron oferta**, no cuántos fueron habilitados o pasaron a la evaluación
  final — es una aproximación razonable pero no perfecta al concepto de "competencia real".
- Solo se cubren 3 meses (junio-agosto 2026); una entidad con pocos procesos en esa ventana puede
  no ser representativa de su comportamiento anual.
