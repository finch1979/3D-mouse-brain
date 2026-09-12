# Adult mouse systems: evidence and rendering contract

Prepared 2026-09-12. Scope: educational adult mouse regional anatomy, not a complete connectome. No journal figures are reproduced. The Markdown evidence ledger precedes the new model registry; its IDs are carried into build manifests and reader citations.

## Atlas and licensing

- `CCF`: Allen Mouse CCFv3 2017 structure meshes, adult reference space. Ontology: https://api.brain-map.org/api/v2/structure_graph_download/1.json ; mesh source: https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/annotation/ccf_2017/structure_meshes/{id}.obj . Labels and IDs are resolved against mouse structure graph 1, not a human ontology.
- Cite Allen Institute and the specific dataset, under https://alleninstitute.org/legal/terms-of-use and https://alleninstitute.org/citation-policy/ . The source terms allow research/noncommercial use; this release is the existing public educational atlas, not a sale or commercial service. Do not describe these meshes as unrestricted CC BY or grant commercial redistribution rights. Any later commercial reuse needs separate license review.
- Meshes describe anatomical regions, not the cell populations in experiments. Research ages, strains and cell types may differ from the atlas reference. This is registration for explanation, not registration of the original experimental specimens.
- All links below supply factual evidence only. Text is paraphrased; no paper images, tables, or publisher assets are embedded.

## Evidence ledger

Each row lists the exact regional connection allowed for the first release. Extra context regions are not automatically connected. Arrows are schematic relationships, not measured trajectories, strengths or conduction speeds.

| ID / system | Mouse evidence | Allowed display / limitations |
|---|---|---|
| A1 auditory | [Inhibitory projections in the mouse auditory tectothalamic system](https://pmc.ncbi.nlm.nih.gov/articles/PMC6025108/) | IC → MGv as a regional summary; not every IC neuron targets MGv. Show ipsilateral main branch; omit contralateral collateral detail. CN and SOC are anatomical context, not a fabricated serial chain. |
| A2 auditory | [Auditory thalamocortical synaptic transmission in vitro](https://journals.physiology.org/doi/full/10.1152/jn.00549.2001) | MGv → AUDp. Brain-slice mouse evidence, displayed in adult atlas space; not a developmental claim. |
| T1 somatosensory | [Circuit organization of the excitatory sensorimotor loop through hand/forelimb S1 and M1](https://elifesciences.org/articles/66836) | CU left → VPL right → SSp-ul right → MOp right. Crossed cuneothalamic segment represented without claiming a traced course. GR and SSp-ll are lower-body context only. Whisker pathway remains its separate page. |
| G1 gustatory | [Afferent connections of the parabrachial nucleus in C57BL/6J mice](https://pmc.ncbi.nlm.nih.gov/articles/PMC2705209/) | NTS → PB. Whole NTS/PB outlines are regional context, not isolated taste-cell subdivisions. |
| G2 gustatory | [Satb2 neurons in the parabrachial nucleus mediate taste perception](https://pmc.ncbi.nlm.nih.gov/articles/PMC7801645/) | PB → VPMpc → GU. GU is the atlas gustatory area; the mesh is not a reconstruction of the experimental insular taste ensemble. Keep the mouse PB relay. |
| V1 vestibular | [Multiple types of cerebellar target neurons and their circuitry in the vestibulo-ocular reflex](https://pmc.ncbi.nlm.nih.gov/articles/PMC3227528/) | FL right → MV right; Purkinje-cell inhibitory influence. Whole FL/MV are context for this cell-specific connection. |
| V2 vestibular | [Mouse medial vestibular nucleus neurons projecting to the oculomotor nucleus](https://journals.physiology.org/doi/full/10.1152/jn.00796.2005) | MV → III. Present as a regional projection; no detailed eye-muscle or synaptic-sign assignment. SUV and VI remain context. |
| C1 cerebellum | [Cerebellar nuclei evolved by repeatedly duplicating a conserved cell-type set](https://pmc.ncbi.nlm.nih.gov/articles/PMC8510508/) | IP right → RN left and IP right → VAL left, regional output examples. FN, DN, CBX and IO are independently switchable context. Do not imply all cerebellar output travels through IP. |
| C2 cerebellum | [Input and output organization of the mesodiencephalic junction](https://pmc.ncbi.nlm.nih.gov/articles/PMC9300004/) | IO → contralateral CBX, climbing-fiber input at regional scale. Individual olivocerebellar modules are not segmented. |
| C3 cerebellum | [Diverse inhibitory projections from the cerebellar interposed nucleus](https://elifesciences.org/articles/66231) | Direct mouse intersectional tracing support for interposed outputs to RN and VAL. Use regional projections without assigning a single transmitter sign to the entire nucleus. |
| L1 limbic | [BLA to vHPC inputs modulate anxiety-related behaviors](https://pubmed.ncbi.nlm.nih.gov/23972595/) | BLA → ventral hippocampal CA1 neighborhood. Whole CA1 is context; a wireframe vCA1 anchor is only an approximate subregional location, never a real vCA1 segmentation. |
| L2 limbic | [Posterior BLA to ventral hippocampal CA1 drives approach behaviour](https://pmc.ncbi.nlm.nih.gov/articles/PMC6954243/) | Explain heterogeneous effects across BLA/CA1 populations. Do not label the entire BLA→CA1 link universally anxiogenic or anxiolytic. DG/CA3/SUB/ENTl are context; hippocampal detail has its own existing page. |
| P1 pain | [Elucidating an affective pain circuit that creates a threat memory](https://pmc.ncbi.nlm.nih.gov/articles/PMC4512641/) | PB → CEA as the ascending affective component. Peripheral and spinal stages described in guide, not assigned arbitrary adult brain coordinates. PB/CEA meshes do not isolate CGRP populations. |
| P2 pain | [Yin-and-yang bifurcation of opioidergic circuits for descending analgesia](https://pmc.ncbi.nlm.nih.gov/articles/PMC6205495/) | PAG → RVM neighborhood, approximate wireframe anchor near RM; RM is not identical to RVM. No fabricated spinal mesh. Descending modulation is not always inhibition. |
| S1 sleep | [Mechanism for hypocretin-mediated sleep-to-wake transitions](https://pmc.ncbi.nlm.nih.gov/articles/PMC3465396/) | LHA orexin neighborhood → LC. Whole LHA does not identify orexin neurons; use a schematic population marker. |
| S2 sleep | [Identification of preoptic sleep neurons using retrograde labelling and gene profiling](https://pmc.ncbi.nlm.nih.gov/articles/PMC5554302/) | Preoptic population → TMv region. Use an explicitly approximate POA population marker near preoptic atlas regions; do not equate the experiment with the entire VLPO. GABAergic sleep-promoting projection; not a complete sleep flip-flop model. |
| U1 autonomic | [Central afferents to the NTS in rats and mice](https://pmc.ncbi.nlm.nih.gov/articles/PMC7942812/) | PVH → NTS; use mouse tracing results, not rat-only connections. |
| U2 autonomic | [NTS A2 neurons control feeding via projections to PVH](https://www.nature.com/articles/s41386-022-01448-5) | NTS → PVH; whole regions are context for the A2-related circuit, not a generic excitatory autonomic reflex. |
| U3 autonomic | [Cyto- and chemoarchitecture of PVH in C57BL/6J male mouse](https://pmc.ncbi.nlm.nih.gov/articles/PMC4104804/) | PVH → dorsal vagal complex neighborhood, schematic population/target marker near DMX/NTS. Tracer fields include adjacent nuclei: do not claim isolated monosynaptic PVH→DMX specificity. |

## Geometry and uncertainties

Resolve exact acronyms before fetch; retain source ID, URL and checksum. Convert PIR micrometres to right/anterior/superior with `(z,-x,-y)`, center every region using the same root bounds. Keep both hemispheres in anatomical meshes; choose left/right anchors explicitly for each route. Real regional anchors use a vertex nearest the hemisphere centroid, never a midpoint in empty space. Approximate populations use wireframe markers and bilingual labels. Tube paths interpolate endpoints for readability only, with no diffusion tractography claim.

Missing meshes stop the affected build with the exact acronym; no silent human substitute, fake shape, or omitted required structure. A future verified fallback must be documented here before use.

## Reader presentation

Each new page includes bilingual scope, selected connection steps, source links, limitations, Allen attribution, Finch educational disclaimer, and links to related mouse pages where applicable. Guides hold explanations, while the model starts clear on mobile. No neural pulse is enabled: tube color identifies branches and is not a timing or firing measurement.
