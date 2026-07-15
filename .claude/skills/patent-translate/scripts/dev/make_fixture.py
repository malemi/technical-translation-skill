#!/usr/bin/env python3
"""Build projects/_fixture/source.docx from the literal fixture text.

The Italian text below is copied EXACTLY from projects/_fixture/fixture_spec.md
(decimal commas, micro sign, numeral suffixes are test data — do not touch).
One paragraph per line; an empty paragraph is inserted between consecutive
text lines so that ingest's empty-paragraph handling is exercised. Run from
the repo root. Output content is deterministic (fixed core properties; zip
member timestamps are whatever zipfile stamps and are not content).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docx import Document

OUT_PATH = Path("projects/_fixture/source.docx")

TEXT_LINES = [
    'TITOLO',
    "Apparecchiatura per l'estrazione a freddo di caffè e relativo metodo di estrazione",
    'RIASSUNTO',
    "Apparecchiatura (1) per l'estrazione a freddo di caffè comprendente una vasca di estrazione (2) atta a contenere acqua e caffè macinato, un gruppo filtrante (3) disposto all'interno della vasca di estrazione (2), e una pompa di ricircolo (4) configurata per far circolare l'acqua attraverso il gruppo filtrante (3). L'apparecchiatura comprende inoltre un'unità di controllo (5) che regola la temperatura dell'acqua tra 4 °C e 8 °C e la pressione di esercizio fino a 12,5 bar. È inoltre descritto un metodo di estrazione a freddo impiegante detta apparecchiatura.",
    'DESCRIZIONE',
    'CAMPO TECNICO',
    "La presente invenzione riguarda un'apparecchiatura per l'estrazione a freddo di caffè, nonché un metodo di estrazione impiegante tale apparecchiatura.",
    'STATO DELLA TECNICA',
    'Sono noti sistemi per la preparazione di caffè mediante estrazione a freddo, nei quali il caffè macinato è posto a contatto con acqua a temperatura ambiente per tempi di estrazione tipicamente compresi tra 12 e 24 ore. Tali sistemi presentano tuttavia consumi energetici elevati e una resa aromatica limitata. Essa risulta inoltre difficilmente controllabile.',
    'BREVE DESCRIZIONE DELLE FIGURE',
    "La figura 1 mostra una vista schematica dell'apparecchiatura secondo l'invenzione.",
    'La figura 2 mostra una sezione del gruppo filtrante.',
    'DESCRIZIONE DETTAGLIATA',
    "Con riferimento alla figura 1, l'apparecchiatura (1) comprende una vasca di estrazione (2) realizzata in acciaio inossidabile, avente una capacità compresa tra 5 e 50 litri.",
    'Il gruppo filtrante (3) comprende una rete metallica con maglie da 100 µm e un supporto (3a) removibile.',
    'La pompa di ricircolo (4) è configurata per operare a una pressione compresa tra 0,5 bar e 12,5 bar, preferibilmente pari a 2,5 bar.',
    "L'unità di controllo (5) comprende un sensore di temperatura (6) e un temporizzatore (7). Il serbatoio (2) è mantenuto a una temperatura compresa tra 4 °C e 8 °C per un tempo di almeno 20 minuti.",
    "In una forma di realizzazione preferita, la percentuale di caffè macinato rispetto all'acqua è compresa tra il 5% e il 12,5% in peso.",
    "Naturalmente, senza pregiudizio per il principio dell'invenzione, i dettagli di realizzazione potranno variare rispetto a quanto descritto.",
    'RIVENDICAZIONI',
    "1. Apparecchiatura (1) per l'estrazione a freddo di caffè, comprendente:",
    'una vasca di estrazione (2) atta a contenere acqua e caffè macinato;',
    "un gruppo filtrante (3) disposto all'interno della vasca di estrazione (2);",
    "una pompa di ricircolo (4) configurata per far circolare l'acqua attraverso il gruppo filtrante (3);",
    "caratterizzata dal fatto che comprende inoltre un'unità di controllo (5) configurata per mantenere la temperatura dell'acqua tra 4 °C e 8 °C.",
    '2. Apparecchiatura secondo la rivendicazione 1, in cui la vasca di estrazione (2) è realizzata in acciaio inossidabile e presenta una capacità compresa tra 5 e 50 litri.',
    '3. Apparecchiatura secondo la rivendicazione 2, in cui il gruppo filtrante (3) comprende una rete metallica con maglie da 100 µm.',
    '4. Apparecchiatura secondo una qualsiasi delle rivendicazioni da 1 a 3, in cui la pompa di ricircolo (4) è costituita da una pompa centrifuga a velocità variabile.',
    "5. Apparecchiatura secondo la rivendicazione precedente, comprendente inoltre un sensore di pressione (8) collegato all'unità di controllo (5).",
    "6. Metodo di estrazione a freddo di caffè mediante un'apparecchiatura secondo una qualsiasi delle rivendicazioni precedenti, comprendente le fasi di:",
    'introdurre acqua e caffè macinato nella vasca di estrazione (2);',
    "far circolare l'acqua mediante la pompa di ricircolo (4) per un tempo di almeno 20 minuti;",
    'mantenere la temperatura tra 4 °C e 8 °C.',
]


def build_paragraphs() -> list[str]:
    paragraphs: list[str] = []
    for i, line in enumerate(TEXT_LINES):
        if i:
            paragraphs.append("")
        paragraphs.append(line)
    return paragraphs


def main() -> int:
    paragraphs = build_paragraphs()
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)

    props = doc.core_properties
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    props.created = fixed
    props.modified = fixed
    props.author = "make_fixture"
    props.last_modified_by = "make_fixture"
    props.title = "patent-translate fixture"
    props.revision = 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))

    # self-check: reopen and compare paragraph texts with the intended list
    reopened = [p.text for p in Document(str(OUT_PATH)).paragraphs]
    if reopened != paragraphs:
        raise SystemExit(
            f"ERROR: reopened docx does not match intended paragraphs "
            f"({len(reopened)} vs {len(paragraphs)})"
        )

    non_empty = sum(1 for p in paragraphs if p)
    print(f"wrote {OUT_PATH}: {len(paragraphs)} paragraphs ({non_empty} non-empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
