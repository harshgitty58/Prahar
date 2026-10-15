# Situation report — Dharali (event 2025-08-05 08:15 UTC)

*Generated automatically by PRAHAR Space mode from Sentinel-1 radar, Sentinel-2 where clear, Copernicus DEM and pre-event OpenStreetMap (2025-08-04). Every number below comes from the system's maps.*

## Where did the flood hit?
- Detector: **AI U-Net (Kuro Siwo) within the 200 m river corridor + Sentinel-2 MNDWI new water where clear**.
- Flooded area inside the 200 m river corridor: **1.296 km²** (AI 0.446 km² + Sentinel-2 0.85 km²).
- Radar pairs used (same orbit): track 129 ascending 2025-07-24 → 2025-08-05 12:48; track 63 descending 2025-08-01 → 2025-08-07 00:42.
- Not analysable: radar layover/shadow on 1.087 km²; permanent water 1.152 km².
- Sentinel-2 (clear sky): used, S2A_44RKV_20250706_0_L2A → S2C_44RKV_20250813_0_L2A, 40 % of the area clear in both; added 0.85 km² of new open water (MNDWI).

## What was damaged? (pre-event OSM objects on flooded pixels)
- Buildings: **3 of 502**
- Road segments: **13 of 112** · Bridges: **3 of 16**

## Who is cut off? (road connection to nearest AOI exit)
- **1 settlements cut off**: Harsil.
- 0 reachable only by a longer route; 9 still connected; 4 had no mapped road link even before the flood.

## Debris (radar + Sentinel-2)
- The AI model maps floodwater only. Debris = radar change (low confidence) plus Sentinel-2 vegetated→barren change where clear, on the valley floor: **1.466 km²** in the corridor.
- On it: buildings 36 of 502, road segments 14 of 112, bridges 2 of 16; settlements cut off if those roads are blocked: 1.
- Confidence: radar change 1.424 km², Sentinel-2 vegetated→barren 0.042 km²; **both agree on 0.0 km²** (medium confidence).

## Rescue priorities (cut-off settlements, largest first)
- Buildings = pre-event OSM buildings nearest to the settlement. Landing site = flat, dry, open 30 × 30 m patch off the river channel (ICAO Annex 14 Vol II slope limits); crew must check obstacles.
- **Harsil** (village): ≈120 buildings · cut off by water · nearest landing candidate 31.0392, 78.73781 (1.25 km)
- **Bagori** (village): ≈32 buildings · cut off by debris · nearest landing candidate 31.0392, 78.73781 (0.37 km)

## Model reliability
- U-Net trained on Kuro Siwo; on unseen test events: flood precision 0.74, recall 0.82, F1 0.78, IoU 0.64 (flood threshold 0.8, chosen on validation).
- Read as: about 74 % of pixels it calls flooded are flooded, and it finds about 82 % of flooded pixels.

*Answered in 5 min 35 s from raw satellite data.*

## हिन्दी सारांश
- बाढ़ क्षेत्र (नदी के 200 मी गलियारे में): 1.296 वर्ग किमी
- पानी में: इमारतें 3, सड़क खंड 13, पुल 3 · मलबे पर: इमारतें 36, सड़क खंड 14, पुल 2
- संभावित मलबा क्षेत्र: 1.466 वर्ग किमी (कम/मध्यम विश्वसनीयता)
- सड़क संपर्क से कटे गाँव: 2 — Harsil, Bagori
- हेलीकॉप्टर उतरने के संभावित स्थान ऊपर सूची में (ज़मीनी जाँच ज़रूरी)
- स्वचालित उपग्रह अनुमान — कार्रवाई से पहले ज़मीनी पुष्टि करें।

## नेपाली सारांश
- बाढी क्षेत्र (नदीको २०० मि. करिडोरभित्र): 1.296 वर्ग कि.मि.
- पानीमा: भवन 3, सडक खण्ड 13, पुल 3 · लेदो-गेग्रानमा: भवन 36, सडक खण्ड 14, पुल 2
- सम्भावित लेदो-गेग्रान क्षेत्र: 1.466 वर्ग कि.मि. (कम/मध्यम विश्वसनीयता)
- सडक सम्पर्क टुटेका बस्ती: 2 — Harsil, Bagori
- हेलिकप्टर अवतरणका सम्भावित स्थान माथिको सूचीमा (स्थलगत जाँच आवश्यक)
- स्वचालित भू-उपग्रह अनुमान — कारबाही अघि स्थलगत पुष्टि गर्नुहोस्।

## Limitations (read before acting)
- Sentinel-1 revisits every 6–12 days: this maps what the satellite saw, not the moment of the flood, and cannot warn in advance.
- Steep Himalayan slopes cause radar layover/shadow; narrow gorges and debris under forest can be missed.
- OSM completeness varies; unmapped buildings and roads cannot be counted. Damage = 'on a flooded/debris pixel', not structural damage; roads are cut only on the stretches that touch one.
- Floodwater more than 15 m above the nearest mapped drainage is excluded (HAND rule, Twele et al. 2016); flooding fed by unmapped streams can be missed. Debris is not height-limited.
- Educational prototype — verify on the ground before operational use.

*Contains modified Copernicus Sentinel data 2025–2026. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors (pre-event snapshot via the ohsome API). Training data: Kuro Siwo (Bountos et al., NeurIPS 2024, CC BY 4.0).*