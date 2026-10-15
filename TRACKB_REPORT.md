# PRAHAR Space mode: Mapping Flood Damage from Space
*Multimodal AI Hackathon 2026, Track B. Team PRAHAR (VIT). Educational prototype.*

## 1. What the system does
**Input:** an area (W, S, E, N) and a flood date and time.

**Output:** three answers for rescue teams, plus a one-page situation report generated from the maps:
1. **Where did the flood hit?** A flood map from Sentinel-1 radar, before vs after the event, on the same orbit track.
2. **What was damaged?** Pre-event OpenStreetMap buildings, roads and bridges that lie on flooded pixels.
3. **Who is cut off?** Settlements that lose their road connection to the nearest hospital or town (or, if none is mapped, the edge of the area), from a road-network graph with flooded segments and bridges removed.

Run end to end from raw data for any area and date:
```bash
python -m src.space.run    --name <event> --bbox W,S,E,N --date "YYYY-MM-DD HH:MM"   # UTC
python -m src.space.report --name <event>   # writes results/space/<event>/sitrep.md + sitrep.html
```
Outputs go to `results/space/<event>/`: `flood_class.tif`, `flood_class_rule.tif`, `*_hit.geojson`, `cutoff.json`, `summary.json` and `map.png`.

## 2. Inputs: only those Track B allows
| Input | Source (keyless) | Use |
|---|---|---|
| Sentinel-1 (VV, VH) | Microsoft Planetary Computer `sentinel-1-rtc` STAC | before and after pairs from the **same relative orbit**, plus a second pre-event image for the AI |
| Sentinel-2 L2A | Element 84 Earth Search STAC | when the sky is clear: per-pixel, only where the scene classification (SCL) is clear both before and after |
| Copernicus DEM GLO-30 | AWS Open Data `copernicus-dem-30m` | radar layover/shadow geometry, DEM input to the AI |
| OpenStreetMap **before the event** | ohsome API, `elementsFullHistory/geometry`, keeping versions valid at the snapshot date | buildings, roads, bridges, places, hospitals, waterways, water areas |
| Kuro Siwo GRD | Hugging Face `orion-ai-lab/Kuro-Siwo-Webdataset` | training and testing the segmentation model |

Copernicus EMS / UNOSAT maps and post-event OSM are **not** used as inputs. The anonymous ohsome `/elements/geometry` endpoint is blocked, so the full-history endpoint is filtered to the snapshot date. This returns the same features.

## 3. Method
**3.1 Rule baseline: the UN-SPIDER Recommended Practice (UNOOSA).**
- VH in dB, 50 m circular smoothing.
- Difference = after / before, flooded where the difference is > 1.25.
- Permanent water masked; pixels with ≤ 8 connected neighbours removed.

Two documented adaptations, plus one corridor rule:
1. **Mountains.** The practice's slope > 5 % mask removed **99.6 %** of the Dharali valley (263.6 of 264.6 km²). We replaced it with the standard SAR geometry masks:
   - layover where terrain facing the radar is steeper than the local incidence angle;
   - shadow where terrain facing away is steeper than 90° minus the incidence angle;
   - incidence from Sentinel-1 IW's 29.1°–46.0° range across the swath; computed per orbit from GLO-30.

   Only 1.1 km² is then hidden from both orbits.
2. **Permanent water** comes from pre-event OSM water areas, because JRC Global Surface Water is not an allowed input.
3. **Corridor.** Detections are kept only within **200 m of a pre-event mapped river or stream**. This is the Uttarakhand High Court's (2013) river no-construction corridor. Without it, a 12-day monsoon pair flags whole wet hillsides.

**3.2 AI component: flood segmentation (primary detector).**
- **Model:** U-Net with a ResNet-34 encoder, 7 input channels: post-event VV and VH, pre-event 1 VV and VH, pre-event 2 VV and VH (all in dB), and the DEM minus its chip mean. 3 output classes: no water, permanent water, flood.
- **Training:** Kuro Siwo GRD, official train split, streamed from Hugging Face. Loss = cross-entropy + Dice. AdamW, mixed precision, Colab T4. Two time-boxed runs:
  1. 750 steps on 2 shards;
  2. continued for **1,606 more steps** with a stronger flood class weight (3.0), cosine learning rate, and the 3 shards the first run never saw.
- **Decision threshold:** the flood-probability cut-off (**0.80**) was chosen to maximise F1 on the **validation** split (unseen events). The test split was used once, afterwards.
- **Export:** ONNX, run on CPU by `src/space/ai.py`, which applies the same threshold.

**3.3 Sentinel-2 when the sky is clear** (`src/space/optical.py`). For the pre-event (30 days) and post-event (12 days) windows, the scene with the largest **clear share inside the area** is chosen; tile-wide cloud cover says little about one valley. Only pixels that are clear in both images are used (SCL vegetation, bare, water or unclassified):
- **New open water:** MNDWI = (green − SWIR1)/(green + SWIR1) > 0 after and ≤ 0 before (Xu 2006). It joins the AI flood map inside the corridor.
- **Debris / scour:** vegetated before (NDVI ≥ 0.2) and barren after (NDVI ≤ 0.1), using the USGS NDVI ranges (≤ 0.1 barren rock or sand; 0.2–0.3 shrub and grassland). It joins the radar debris layer, and pixels where radar *and* optical agree are marked medium confidence.

**3.4 Clean-up rules**
- **Minimum cluster, on every layer** (AI water, Sentinel-2 water, radar and optical debris): a pixel with ≤ 8 connected neighbours is removed. This is the UN-SPIDER rule, now applied beyond the radar baseline.
- **Height above drainage, on water layers only:** water more than **15 m above the nearest drainage** is excluded (HAND rule, Twele et al. 2016).
  - HAND is computed from the Copernicus DEM, with pre-event OSM waterways and permanent water as the drainage, using the nearest drainage pixel by distance.
  - This removed water blobs on shaded forest slopes and cloud-shadow edges, which floodwater cannot reach.
- **We tested HAND on debris too and rejected it.** At Trishuli it raised area precision to 0.97, but cut the EMS-damaged buildings found from 68 % to 26 %. A glacial-lake outburst throws debris far above 15 m on gorge walls; Twele's rule is a floodwater rule.

**3.5 Damage and cut-off** (`src/space/impact.py`):
- A building counts as **hit** if any flood or debris pixel touches it (direct overlay, no scoring).
- Roads and bridges are checked **segment by segment** (each pair of OSM vertices, sampled every half pixel). Only the damaged stretches are cut from the road graph, so one touched pixel no longer removes a whole highway.
- The road graph is built from pre-event OSM lines, weighted by length. Hit segments are removed. Dijkstra shortest paths to the destinations; settlement status is *cut off*, *longer route*, *connected*, or *not connected even before the flood*.

**3.6 Rescue add-ons** (`src/space/rescue.py`):
- **Who first:** pre-event OSM buildings are assigned to their nearest mapped settlement, and cut-off settlements are ranked by size.
- **Where a helicopter can land:** flat, dry, open patches following ICAO Annex 14 Vol II (Heliports):
  - FATO mean slope ≤ 3 %, no local slope > 5 %;
  - side ≥ 1.5 × D, where D = 15.9 m for the ALH Dhruv used in Himalayan rescue, so a 30 × 30 m patch;
  - not on detected flood/debris, permanent water, the mapped river channel or any pre-event building.

  The nearest three per cut-off settlement are listed in the sitrep and on the map.
- **Flood-path tracer (bonus):**
  - D8 flow directions on a Priority-Flood filled Copernicus DEM (Barnes et al. 2014).
  - Click any upstream point in the dashboard to get the downstream path, plus the settlements and bridges within 200 m of it, with distance from the source.

**3.7 Live use.** The dashboard's "Map any flood" box (API mode) posts an area and date to `POST /space/run`. The pipeline then runs from raw data with stage-by-stage progress, and the result appears as a new event tab. Radar scenes are cached on disk, so repeat runs are faster. The sitrep adds one-glance summaries in **Hindi and Nepali**: fixed, translated sentence templates filled only with the system's numbers (no machine translation, no language model).

## 4. Results
**4.1 AI model on unseen Kuro Siwo test events** (official test split, never seen in training or threshold selection; 3,000 chips):

| Flood class | Run 1 (750 steps, arg-max) | Run 2, arg-max | **Run 2, tuned threshold 0.80** |
|---|---|---|---|
| Precision | 0.566 | 0.592 | **0.739** |
| Recall | 0.168 | 0.892 | **0.823** |
| F1 | 0.259 | 0.712 | **0.779** |
| IoU | 0.149 | 0.553 | **0.638** |

**Any water** (permanent + flood, threshold 0.925): precision 0.861, recall 0.720, **F1 0.784**, IoU 0.645.

Reading: run 1 was badly under-trained, finding only 17 % of flooded pixels. More training on unseen shards lifted recall to 89 %. The validation-chosen threshold then traded a little recall for much higher precision. Now about 3 in 4 pixels called flooded are flooded, and about 4 in 5 flooded pixels are found.

**4.2 Unseen Himalayan scene: Dharali, Uttarkashi (5 Aug 2025, 08:15 UTC).**

AOI 78.70–78.90 E, 30.98–31.10 N (265 km²). Radar pairs:
- track 129 ascending: 24 Jul → **5 Aug 12:48 UTC**, about 4.5 h after the flood;
- track 63 descending: 1 Aug → 7 Aug.

| | **AI floodwater** (run 2, threshold 0.80) | Possible debris (rule radar change, low confidence) |
|---|---|---|
| Area inside the 200 m corridor | **0.74 km²** | 4.77 km² |
| Buildings on it (of 502 pre-event OSM) | **0** | 47 |
| Road segments (of 112) | **0** | 23 |
| Bridges (of 16) | **0** | 1 |
| Settlements cut off (of 14 mapped places) | **0** | 6: Bagori, Bhaironghati, Dhakroliya, Halunga, **Harsil**, Lanka |

**Why the AI map is nearly empty at Dharali:** the disaster was a **debris flow** of mud and boulders that buried the village, not standing floodwater. The U-Net is trained on Kuro Siwo *floodwater* labels, so it correctly does not call rough debris "water".
- The under-trained run-1 model had flagged 9 buildings there. Those were most likely false positives; run 2's much higher precision on unseen events supports that.
- Damage from debris is therefore reported from a separate, clearly labelled low-confidence layer: the rule-based radar change, after/before < 1/1.25 within the corridor.
- That layer's cut-off result (Harsil and five other settlements) is consistent with reports that the road at Harsil was washed out, but the layer itself has not been validated.

Figure: `results/space/dharali/map.png`. The dashboard's "Space mode" page shows both layers interactively.

**Update with Sentinel-2 fusion** (re-run on the same inputs).
- Sentinel-2 of 13 Aug 2025 was 42 % clear over the area. Its MNDWI adds **0.85 km² of new open water** in the corridor, which may include the debris-dammed lake reported near Harsil (not verified here).
- The final flood map (AI + Sentinel-2) hits 3 buildings, 13 road segments and 3 bridges. It cuts off 1 settlements.
- With debris added, 1 are cut off.
- Rescue priorities: Harsil (≈120 buildings, landing candidate 1.25 km), Bagori (≈32 buildings, landing candidate 0.37 km).
- Run time 5 min 35 s.

**4.3 Case study: Trishuli GLOF, Rasuwa, Nepal (25–26 Aug 2026), checked against Copernicus EMS EMSR927.**

The pipeline was run blind for AOI 85.30–85.40 E, 28.14–28.29 N with event time 2026-08-25 22:00 UTC, in **7 min 41 s** from raw data:
- radar pairs: track 85 ascending 2026-08-16 → 2026-08-28 12:21 UTC; track 121 descending 2026-08-19 → 2026-08-31 00:10 UTC; track 19 descending 2026-08-24 → 2026-09-05 00:18 UTC;
- Sentinel-2 S2C_45RUM_20260812_0_L2A → S2B_45RUM_20260827_0_L2A (45 % of the area clear in both);
- OSM snapshot 2026-07-27.

EMSR927 vectors were then downloaded **only to check the output**: the "observed event" polygons and graded buildings and roads for AOI01 Syapru Besi and AOI02 Timure, mapped from WorldView-3 and Legion images of 27 Aug. EMS mapped the event as **"Landslide"**, a debris flow, not standing water. Scores are computed only inside these AOIs (6.426 km²; EMS event area 2.404 km²).

| PRAHAR layer (inside EMS AOIs) | Area precision | Area recall | IoU | EMS-damaged buildings found | EMS-damaged roads found |
|---|---|---|---|---|---|
| Floodwater (AI + Sentinel-2 MNDWI) | 0.97 | 0.03 | 0.03 | 20/864 | 12/35 |
| Debris (radar ∪ Sentinel-2 vegetated→barren) | 0.95 | 0.33 | 0.32 | 571/864 | 23/35 |
| **Both layers** | **0.95** | **0.35** | **0.35** | **578/864 (67 %)** | **24/35 (69 %)** |
| *Ablation: radar debris only* | 0.62 | 0.03 | 0.03 | 2/864 | 4/35 |
| *Ablation: Sentinel-2 debris only* | 1.00 | 0.31 | 0.31 | 570/864 | 23/35 |

Building precision from our side: of the 396 pre-event OSM buildings PRAHAR flags inside the AOIs, **381 (96 %) lie within 25 m of an EMS-damaged building**. EMS grades only damaged buildings, so the EMS side gives recall only.

**Reading.**
- When PRAHAR says "hit", it is almost always right: area precision 0.95, building precision 0.96.
- It finds about two-thirds of the damaged buildings and roads, but only 35 % of the EMS event *area*. Of the missed area, 46 % was under cloud in the post-event Sentinel-2 image; where Sentinel-2 was clear, recall is 0.50 and IoU 0.49.
- The ablation is the honest lesson. In this narrow gorge **radar alone found very little** (recall 0.03): debris is rough, like the forest it replaced, and the steep walls cause layover and shadow. **Sentinel-2's vegetated→barren change carried the result** (precision 1.00).
- As at Dharali, the Kuro Siwo U-Net found essentially no standing water (0.0 km²), which is consistent with EMS calling it a debris flow. The floodwater row comes from Sentinel-2 MNDWI.
- This is also the **unseen-Himalayan test** of the AI component: as a floodwater model it correctly abstains on a debris flow. The damage answer needs the debris evidence.

**Cut-off.**
- The only mapped hospital is at the south end of the valley. **23 of 25 settlements** lose their road link to it, because the one valley road (Pasang Lhamu Highway) runs through the hit corridor.
- EMS independently graded the highway segments in both AOIs as damaged or possibly damaged.
- Largest isolated places with the nearest helicopter landing candidate: .

Error map: `results/space/trishuli/emsr_check.png`. Green = both agree, red = PRAHAR only, blue = EMS only, yellow = EMS-damaged buildings.

## 5. Limitations (what the system cannot do)
- **Revisit.** Sentinel-1 passes every 6–12 days. The map shows what the satellite saw on that pass, not the peak of the flood, and it **cannot warn** of a sudden glacier collapse or cloudburst.
- **Steep terrain.** Radar layover and shadow hide parts of narrow gorges. Only local (active) layover/shadow is modelled; shadow cast by distant ridges is not.
- **Monsoon change.** Between two passes 12 days apart, wet slopes and vegetation change the backscatter. The rule baseline over-detects; the 200 m corridor limits but does not remove this.
- **AI model.** F1 0.78 on Kuro Siwo's unseen test events, which are mostly lowland and river floods. Himalayan gorges differ: at Trishuli (EMSR927) the model correctly found no standing water in a debris flow, so damage there comes from the debris evidence. It was trained on GRD σ⁰ but run on RTC γ⁰, which shifts the input distribution. Debris deposits are not a separate class, and training was time-boxed (about 2,350 steps in total).
- **OSM.** Buildings and roads that aren't mapped can't be counted. "Hit" means the object lies on a flooded pixel, not that it is structurally damaged. Settlement-to-road snapping can misplace hamlets.
- Sentinel-2 helps only where the sky is clear: at Trishuli 45 % of the area was clear after the event, so cloudy parts rely on radar alone, which is weak on debris in narrow gorges.
- Results are estimates for an educational prototype. Verify on the ground before any operational use.

## 6. Attribution and citations
- Contains modified Copernicus Sentinel data 2025–2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- © OpenStreetMap contributors.
- Bountos, N.I. et al. (2024). *Kuro Siwo: 33 billion m² under the water. A global multi-temporal satellite dataset for rapid flood mapping.* NeurIPS Datasets & Benchmarks. CC BY 4.0.
- UN-SPIDER (UNOOSA). *Recommended Practice: Flood Mapping and Damage Assessment using Sentinel-1 SAR Data in Google Earth Engine.*
- Copernicus Global Flood Monitoring, Product User Manual v4.0 (2025): exclusion-mask concepts (radar shadow, topography).
- Uttarakhand High Court (Aug 2013), 200 m river corridor; NGT (2017) river setbacks.
