# Situation report — Trishuli (event 2026-08-25 22:00 UTC)

*Generated automatically by PRAHAR Space mode from Sentinel-1 radar, Sentinel-2 where clear, Copernicus DEM and pre-event OpenStreetMap (2026-07-27). Every number below comes from the system's maps.*

## Where did the flood hit?
- Detector: **AI U-Net (Kuro Siwo) within the 200 m river corridor + Sentinel-2 MNDWI new water where clear**.
- Flooded area inside the 200 m river corridor: **0.677 km²** (AI 0.0 km² + Sentinel-2 0.677 km²).
- Radar pairs used (same orbit): track 85 ascending 2026-08-16 → 2026-08-28 12:21; track 121 descending 2026-08-19 → 2026-08-31 00:10; track 19 descending 2026-08-24 → 2026-09-05 00:18.
- Not analysable: radar layover/shadow on 2.254 km²; permanent water 0.341 km².
- Sentinel-2 (clear sky): used, S2C_45RUM_20260812_0_L2A → S2B_45RUM_20260827_0_L2A, 45 % of the area clear in both; added 0.677 km² of new open water (MNDWI).

## What was damaged? (pre-event OSM objects on flooded pixels)
- Buildings: **27 of 3074**
- Road segments: **42 of 389** · Bridges: **9 of 32**

## Who is cut off? (road connection to nearest hospital)
- **23 settlements cut off**: Aamachhodingmo, Bahun Danda, Bhanjyang, Bhrajam, Bridhim, Brimdang, Chilime, Dalgaun, Dalphedi, Goljung, Khangjim, Lingling, Nagthali, Pajung, Rasuwa Gadhi, Resuo, Sherpagaun, Surka, Syabru Bensi, Thuman, Timure.
- 0 reachable only by a longer route; 2 still connected; 0 had no mapped road link even before the flood.

## Debris (radar + Sentinel-2)
- The AI model maps floodwater only. Debris = radar change (low confidence) plus Sentinel-2 vegetated→barren change where clear, on the valley floor: **1.981 km²** in the corridor.
- On it: buildings 422 of 3074, road segments 54 of 389, bridges 8 of 32; settlements cut off if those roads are blocked: 23.
- Confidence: radar change 0.728 km², Sentinel-2 vegetated→barren 1.306 km²; **both agree on 0.052 km²** (medium confidence).

## Rescue priorities (cut-off settlements, largest first)
- Buildings = pre-event OSM buildings nearest to the settlement. Landing site = flat, dry, open 30 × 30 m patch off the river channel (ICAO Annex 14 Vol II slope limits); crew must check obstacles.
- **Syabru Bensi** (suburb): ≈404 buildings · cut off by water + debris · no landing candidate found
- **Goljung** (suburb): ≈277 buildings · cut off by water + debris · no landing candidate found
- **Thuman** (suburb): ≈265 buildings · cut off by water + debris · no landing candidate found
- **Timure** (suburb): ≈263 buildings · cut off by water + debris · no landing candidate found
- **Chilime** (suburb): ≈166 buildings · cut off by water + debris · no landing candidate found
- **Dalphedi** (hamlet): ≈165 buildings · cut off by water + debris · no landing candidate found
- **Pajung** (hamlet): ≈158 buildings · cut off by water + debris · no landing candidate found
- **Rasuwa Gadhi** (hamlet): ≈148 buildings · cut off by water + debris · no landing candidate found

## Model reliability
- U-Net trained on Kuro Siwo; on unseen test events: flood precision 0.74, recall 0.82, F1 0.78, IoU 0.64 (flood threshold 0.8, chosen on validation).
- Read as: about 74 % of pixels it calls flooded are flooded, and it finds about 82 % of flooded pixels.

*Answered in 7 min 41 s from raw satellite data.*

## हिन्दी सारांश
- बाढ़ क्षेत्र (नदी के 200 मी गलियारे में): 0.677 वर्ग किमी
- पानी में: इमारतें 27, सड़क खंड 42, पुल 9 · मलबे पर: इमारतें 422, सड़क खंड 54, पुल 8
- संभावित मलबा क्षेत्र: 1.981 वर्ग किमी (कम/मध्यम विश्वसनीयता)
- सड़क संपर्क से कटे गाँव: 21 — Syabru Bensi, Goljung, Thuman, Timure, Chilime, Dalphedi, Pajung, Rasuwa Gadhi, Lingling, Aamachhodingmo, Bridhim, Bhrajam, Resuo, Brimdang, Khangjim, Bahun Danda, Bhanjyang, Sherpagaun, Nagthali, Surka, Dalgaun
- हेलीकॉप्टर उतरने के संभावित स्थान ऊपर सूची में (ज़मीनी जाँच ज़रूरी)
- स्वचालित उपग्रह अनुमान — कार्रवाई से पहले ज़मीनी पुष्टि करें।

## नेपाली सारांश
- बाढी क्षेत्र (नदीको २०० मि. करिडोरभित्र): 0.677 वर्ग कि.मि.
- पानीमा: भवन 27, सडक खण्ड 42, पुल 9 · लेदो-गेग्रानमा: भवन 422, सडक खण्ड 54, पुल 8
- सम्भावित लेदो-गेग्रान क्षेत्र: 1.981 वर्ग कि.मि. (कम/मध्यम विश्वसनीयता)
- सडक सम्पर्क टुटेका बस्ती: 21 — Syabru Bensi, Goljung, Thuman, Timure, Chilime, Dalphedi, Pajung, Rasuwa Gadhi, Lingling, Aamachhodingmo, Bridhim, Bhrajam, Resuo, Brimdang, Khangjim, Bahun Danda, Bhanjyang, Sherpagaun, Nagthali, Surka, Dalgaun
- हेलिकप्टर अवतरणका सम्भावित स्थान माथिको सूचीमा (स्थलगत जाँच आवश्यक)
- स्वचालित भू-उपग्रह अनुमान — कारबाही अघि स्थलगत पुष्टि गर्नुहोस्।

## Limitations (read before acting)
- Sentinel-1 revisits every 6–12 days: this maps what the satellite saw, not the moment of the flood, and cannot warn in advance.
- Steep Himalayan slopes cause radar layover/shadow; narrow gorges and debris under forest can be missed.
- OSM completeness varies; unmapped buildings and roads cannot be counted. Damage = 'on a flooded/debris pixel', not structural damage; roads are cut only on the stretches that touch one.
- Floodwater more than 15 m above the nearest mapped drainage is excluded (HAND rule, Twele et al. 2016); flooding fed by unmapped streams can be missed. Debris is not height-limited.
- Educational prototype — verify on the ground before operational use.

*Contains modified Copernicus Sentinel data 2025–2026. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors (pre-event snapshot via the ohsome API). Training data: Kuro Siwo (Bountos et al., NeurIPS 2024, CC BY 4.0).*