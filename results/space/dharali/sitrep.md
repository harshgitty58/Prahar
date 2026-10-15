# Situation report — Dharali (event 2025-08-05 08:15 UTC)

*Generated automatically by PRAHAR Space mode from Sentinel-1 radar, Sentinel-2 where clear, Copernicus DEM and pre-event OpenStreetMap (2025-08-04). Every number below comes from the system's maps.*

## Where did the flood hit?
- Detector: **AI U-Net (Kuro Siwo) within the 200 m river corridor + Sentinel-2 MNDWI new water where clear**.
- Flooded area inside the 200 m river corridor: **2.771 km²** (AI 0.735 km² + Sentinel-2 2.036 km²).
- Radar pairs used (same orbit): track 129 ascending 2025-07-24 → 2025-08-05 12:48; track 63 descending 2025-08-01 → 2025-08-07 00:42.
- Not analysable: radar layover/shadow on 1.087 km²; permanent water 1.152 km².
- Sentinel-2 (clear sky): used, S2A_44RKV_20250706_0_L2A → S2C_44RKV_20250813_0_L2A, 40 % of the area clear in both; added 2.036 km² of new open water (MNDWI).

## What was damaged? (pre-event OSM objects on flooded pixels)
- Buildings: **7 of 502**
- Road segments: **22 of 112** · Bridges: **4 of 16**

## Who is cut off? (road connection to nearest AOI exit)
- **5 settlements cut off**: Bagori, Bhaironghati, Halunga, Harsil, Lanka.
- 0 reachable only by a longer route; 5 still connected; 4 had no mapped road link even before the flood.

## Possible debris (low confidence)
- The AI model maps floodwater only. A rule-based radar-change layer marks **4.828 km²** of possible debris / ground change in the corridor (not validated).
- On it: buildings 53 of 502, road segments 27 of 112, bridges 2 of 16; settlements cut off if those roads are blocked: 6.
- Confidence: radar change 4.771 km², Sentinel-2 vegetated→barren 0.058 km²; **both agree on 0.001 km²** (medium confidence).

## Rescue priorities (cut-off settlements, largest first)
- Buildings = pre-event OSM buildings nearest to the settlement. Landing site = flat, dry, open 30 × 30 m patch off the river channel (ICAO Annex 14 Vol II slope limits); crew must check obstacles.
- **Harsil** (village): ≈120 buildings · cut off by water + debris · nearest landing candidate 31.0392, 78.73781 (1.25 km)
- **Halunga** (hamlet): ≈45 buildings · cut off by water + debris · nearest landing candidate 31.0392, 78.73781 (0.85 km)
- **Bagori** (village): ≈32 buildings · cut off by water + debris · nearest landing candidate 31.0392, 78.73781 (0.37 km)
- **Lanka** (village): ≈22 buildings · cut off by water + debris · nearest landing candidate 31.09597, 78.80244 (9.6 km)
- **Bhaironghati** (hamlet): ≈18 buildings · cut off by water + debris · nearest landing candidate 31.09597, 78.80244 (9.9 km)
- **Dhakroliya** (hamlet): ≈14 buildings · cut off by debris · nearest landing candidate 31.03732, 78.72991 (0.29 km)

## Model reliability
- U-Net trained on Kuro Siwo; on unseen test events: flood precision 0.74, recall 0.82, F1 0.78, IoU 0.64 (flood threshold 0.8, chosen on validation).
- Read as: about 74 % of pixels it calls flooded are flooded, and it finds about 82 % of flooded pixels.

*Answered in 8 min 3 s from raw satellite data.*

## हिन्दी सारांश
- बाढ़ क्षेत्र (नदी के 200 मी गलियारे में): 2.771 वर्ग किमी
- पानी में: इमारतें 7, सड़क खंड 22, पुल 4 · मलबे पर: इमारतें 53, सड़क खंड 27, पुल 2
- संभावित मलबा क्षेत्र: 4.828 वर्ग किमी (कम/मध्यम विश्वसनीयता)
- सड़क संपर्क से कटे गाँव: 6 — Harsil, Halunga, Bagori, Lanka, Bhaironghati, Dhakroliya
- हेलीकॉप्टर उतरने के संभावित स्थान ऊपर सूची में (ज़मीनी जाँच ज़रूरी)
- स्वचालित उपग्रह अनुमान — कार्रवाई से पहले ज़मीनी पुष्टि करें।

## नेपाली सारांश
- बाढी क्षेत्र (नदीको २०० मि. करिडोरभित्र): 2.771 वर्ग कि.मि.
- पानीमा: भवन 7, सडक खण्ड 22, पुल 4 · लेदो-गेग्रानमा: भवन 53, सडक खण्ड 27, पुल 2
- सम्भावित लेदो-गेग्रान क्षेत्र: 4.828 वर्ग कि.मि. (कम/मध्यम विश्वसनीयता)
- सडक सम्पर्क टुटेका बस्ती: 6 — Harsil, Halunga, Bagori, Lanka, Bhaironghati, Dhakroliya
- हेलिकप्टर अवतरणका सम्भावित स्थान माथिको सूचीमा (स्थलगत जाँच आवश्यक)
- स्वचालित भू-उपग्रह अनुमान — कारबाही अघि स्थलगत पुष्टि गर्नुहोस्।

## Limitations (read before acting)
- Sentinel-1 revisits every 6–12 days: this maps what the satellite saw, not the moment of the flood, and cannot warn in advance.
- Steep Himalayan slopes cause radar layover/shadow; narrow gorges and debris under forest can be missed.
- OSM completeness varies; unmapped buildings and roads cannot be counted. Damage = 'on a flooded pixel', not structural damage.
- Educational prototype — verify on the ground before operational use.

*Contains modified Copernicus Sentinel data 2025–2026. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors (pre-event snapshot via the ohsome API). Training data: Kuro Siwo (Bountos et al., NeurIPS 2024, CC BY 4.0).*