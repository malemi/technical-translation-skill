# Fixture spec — synthetic Italian mini-patent

`dev/make_fixture.py` turns the Italian text below into
`projects/_fixture/source.docx`, one paragraph per line (blank lines = empty
paragraphs are optional and may be omitted). ALL-CAPS lines are headings, each
its own paragraph. Claim feature lines (ending with `;`) are separate
paragraphs belonging to the running claim. Keep the Italian EXACTLY as written:
decimal commas, "µm", numeral suffixes like "(3a)" are test data.

The text contains DELIBERATE source quirks that the pipeline must surface, not
fix:
- "vasca di estrazione (2)" vs "serbatoio (2)": same numeral, two different
  terms → numeral_term_consistency must warn on the IT side.
- "Essa risulta inoltre difficilmente controllabile.": ambiguous antecedent →
  a model-side AMBIGUITY flag at run time (not a mechanical check).
- "sensore di pressione (8)" appears ONLY in claim 5, never in the description
  → claim_support must fail (faithful CLAIM-DEFECT case).
- Claim 4 is multiple-dependent; claim 6 depends on all preceding claims.

Expected ingest results (acceptance for the Foundation phase):
- Sections found: title, abstract, description, claims.
- 6 claims; dependency graph: 1→[], 2→[1], 3→[2], 4→[1,2,3] (multiple),
  5→[4], 6→[1,2,3,4,5] (multiple).
- Numeral inventory contains 1, 2, 3, 3a, 4, 5, 6, 7, 8.
- term_map_it["2"] has two distinct terms.

---

TITOLO

Apparecchiatura per l'estrazione a freddo di caffè e relativo metodo di estrazione

RIASSUNTO

Apparecchiatura (1) per l'estrazione a freddo di caffè comprendente una vasca di estrazione (2) atta a contenere acqua e caffè macinato, un gruppo filtrante (3) disposto all'interno della vasca di estrazione (2), e una pompa di ricircolo (4) configurata per far circolare l'acqua attraverso il gruppo filtrante (3). L'apparecchiatura comprende inoltre un'unità di controllo (5) che regola la temperatura dell'acqua tra 4 °C e 8 °C e la pressione di esercizio fino a 12,5 bar. È inoltre descritto un metodo di estrazione a freddo impiegante detta apparecchiatura.

DESCRIZIONE

CAMPO TECNICO

La presente invenzione riguarda un'apparecchiatura per l'estrazione a freddo di caffè, nonché un metodo di estrazione impiegante tale apparecchiatura.

STATO DELLA TECNICA

Sono noti sistemi per la preparazione di caffè mediante estrazione a freddo, nei quali il caffè macinato è posto a contatto con acqua a temperatura ambiente per tempi di estrazione tipicamente compresi tra 12 e 24 ore. Tali sistemi presentano tuttavia consumi energetici elevati e una resa aromatica limitata. Essa risulta inoltre difficilmente controllabile.

BREVE DESCRIZIONE DELLE FIGURE

La figura 1 mostra una vista schematica dell'apparecchiatura secondo l'invenzione.

La figura 2 mostra una sezione del gruppo filtrante.

DESCRIZIONE DETTAGLIATA

Con riferimento alla figura 1, l'apparecchiatura (1) comprende una vasca di estrazione (2) realizzata in acciaio inossidabile, avente una capacità compresa tra 5 e 50 litri.

Il gruppo filtrante (3) comprende una rete metallica con maglie da 100 µm e un supporto (3a) removibile.

La pompa di ricircolo (4) è configurata per operare a una pressione compresa tra 0,5 bar e 12,5 bar, preferibilmente pari a 2,5 bar.

L'unità di controllo (5) comprende un sensore di temperatura (6) e un temporizzatore (7). Il serbatoio (2) è mantenuto a una temperatura compresa tra 4 °C e 8 °C per un tempo di almeno 20 minuti.

In una forma di realizzazione preferita, la percentuale di caffè macinato rispetto all'acqua è compresa tra il 5% e il 12,5% in peso.

Naturalmente, senza pregiudizio per il principio dell'invenzione, i dettagli di realizzazione potranno variare rispetto a quanto descritto.

RIVENDICAZIONI

1. Apparecchiatura (1) per l'estrazione a freddo di caffè, comprendente:

una vasca di estrazione (2) atta a contenere acqua e caffè macinato;

un gruppo filtrante (3) disposto all'interno della vasca di estrazione (2);

una pompa di ricircolo (4) configurata per far circolare l'acqua attraverso il gruppo filtrante (3);

caratterizzata dal fatto che comprende inoltre un'unità di controllo (5) configurata per mantenere la temperatura dell'acqua tra 4 °C e 8 °C.

2. Apparecchiatura secondo la rivendicazione 1, in cui la vasca di estrazione (2) è realizzata in acciaio inossidabile e presenta una capacità compresa tra 5 e 50 litri.

3. Apparecchiatura secondo la rivendicazione 2, in cui il gruppo filtrante (3) comprende una rete metallica con maglie da 100 µm.

4. Apparecchiatura secondo una qualsiasi delle rivendicazioni da 1 a 3, in cui la pompa di ricircolo (4) è costituita da una pompa centrifuga a velocità variabile.

5. Apparecchiatura secondo la rivendicazione precedente, comprendente inoltre un sensore di pressione (8) collegato all'unità di controllo (5).

6. Metodo di estrazione a freddo di caffè mediante un'apparecchiatura secondo una qualsiasi delle rivendicazioni precedenti, comprendente le fasi di:

introdurre acqua e caffè macinato nella vasca di estrazione (2);

far circolare l'acqua mediante la pompa di ricircolo (4) per un tempo di almeno 20 minuti;

mantenere la temperatura tra 4 °C e 8 °C.
