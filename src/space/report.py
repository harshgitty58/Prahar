"""Space mode — one-page situation report, generated only from the system's own outputs (no hand-typed numbers).

Reads results/space/<name>/{summary.json, cutoff.json} and models/space/floodseg_meta.json and writes
results/space/<name>/sitrep.md and sitrep.html.  Run: python -m src.space.report --name dharali
"""
import argparse
import html
import json

from src.config import PROJECT_ROOT

r2 = lambda v: None if v is None else round(v, 2)  # noqa: E731
ATTRIB = ["Contains modified Copernicus Sentinel data 2025–2026.",
          "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.",
          "© OpenStreetMap contributors (pre-event snapshot via the ohsome API).",
          "Training data: Kuro Siwo (Bountos et al., NeurIPS 2024, CC BY 4.0)."]


# Hindi / Nepali one-glance summaries. Fixed, translated templates; every number and name is filled from the system's
# outputs (no machine translation, no language model -> nothing can be invented).
LOCAL = {
    "हिन्दी सारांश": ["बाढ़ क्षेत्र (नदी के 200 मी गलियारे में): {flood} वर्ग किमी",
                      "पानी में: इमारतें {bw}, सड़क खंड {rw}, पुल {brw} · मलबे पर: इमारतें {bd}, सड़क खंड {rd}, पुल {brd}",
                      "संभावित मलबा क्षेत्र: {deb} वर्ग किमी (कम/मध्यम विश्वसनीयता)",
                      "सड़क संपर्क से कटे गाँव: {n} — {names}",
                      "हेलीकॉप्टर उतरने के संभावित स्थान ऊपर सूची में (ज़मीनी जाँच ज़रूरी)",
                      "स्वचालित उपग्रह अनुमान — कार्रवाई से पहले ज़मीनी पुष्टि करें।"],
    "नेपाली सारांश": ["बाढी क्षेत्र (नदीको २०० मि. करिडोरभित्र): {flood} वर्ग कि.मि.",
                      "पानीमा: भवन {bw}, सडक खण्ड {rw}, पुल {brw} · लेदो-गेग्रानमा: भवन {bd}, सडक खण्ड {rd}, पुल {brd}",
                      "सम्भावित लेदो-गेग्रान क्षेत्र: {deb} वर्ग कि.मि. (कम/मध्यम विश्वसनीयता)",
                      "सडक सम्पर्क टुटेका बस्ती: {n} — {names}",
                      "हेलिकप्टर अवतरणका सम्भावित स्थान माथिको सूचीमा (स्थलगत जाँच आवश्यक)",
                      "स्वचालित भू-उपग्रह अनुमान — कारबाही अघि स्थलगत पुष्टि गर्नुहोस्।"],
}


def flooded(f: dict) -> float:
    """Final flood map inside the corridor: AI (or rule) water plus Sentinel-2 new water where clear."""
    base = f.get("ai_flood_km2_corridor", f.get("water_km2")) or 0
    return round(base + (f.get("s2_added_km2") or 0), 3)


def local_summaries(s, c, rz) -> list:
    f, dm, dr = s["flood"], s["damage"], s.get("debris_rule") or {}
    dd = dr.get("damage", dm)
    names = [r["name"] for r in rz["settlements"]] if rz else sorted({r["name"] for r in c["settlements"] if r["status"] == "CUT OFF" and r["name"]})
    v = {"flood": flooded(f), "deb": dr.get("km2", 0),
         "bw": dm["buildings"]["hit"], "rw": dm["roads"]["hit"], "brw": dm["bridges"]["hit"],
         "bd": dd["buildings"]["hit"] if dr else 0, "rd": dd["roads"]["hit"] if dr else 0, "brd": dd["bridges"]["hit"] if dr else 0,
         "n": len(names), "names": ", ".join(names) or "—"}
    out = []
    for head, lines in LOCAL.items():
        out += [f"## {head}"] + [f"- {t.format(**v)}" for t in lines] + [""]
    return out


def build(name: str) -> str:
    d = PROJECT_ROOT / "results/space" / name
    s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    c = json.loads((d / "cutoff.json").read_text(encoding="utf-8"))
    m = json.loads((PROJECT_ROOT / "models/space/floodseg_meta.json").read_text(encoding="utf-8")) if (PROJECT_ROOT / "models/space/floodseg_meta.json").exists() else {}
    f, dm, s2 = s["flood"], s["damage"], s.get("s2")
    rz = json.loads((d / "rescue.json").read_text(encoding="utf-8")) if (d / "rescue.json").exists() else None
    cut = [r for r in c["settlements"] if r["status"] == "CUT OFF"]
    longer = [r for r in c["settlements"] if r["status"] == "longer route"]
    flood_km2 = flooded(f)
    L = [f"# Situation report — {name.title()} (event {s['event_utc'][:16]} UTC)", "",
         f"*Generated automatically by PRAHAR Space mode from Sentinel-1 radar, Sentinel-2 where clear, Copernicus DEM and pre-event OpenStreetMap ({s['osm_snapshot']}). Every number below comes from the system's maps.*", "",
         "## Where did the flood hit?",
         f"- Detector: **{s.get('detector', 'rule baseline')}**.",
         f"- Flooded area inside the 200 m river corridor: **{flood_km2} km²**" + (f" (AI {f.get('ai_flood_km2_corridor')} km² + Sentinel-2 {f.get('s2_added_km2')} km²)" if f.get("s2_added_km2") else "") + ".",
         f"- Radar pairs used (same orbit): " + "; ".join(f"track {p['orbit']} {p['state']} {p['before_t'][:10]} → {p['after_t'][:16]}" for p in s["s1_pairs"]) + ".",
         f"- Not analysable: radar layover/shadow on {f.get('hidden_all_orbits_km2')} km²; permanent water {f.get('permanent_water_km2')} km².",
         ("- Sentinel-2 (clear sky): " + (f"used, {s2['pre'][:24]} → {s2['post'][:24]}, {round(100 * s2.get('both_clear', 0))} % of the area clear in both; added {f.get('s2_added_km2', 0)} km² of new open water (MNDWI)."
                                          if s2.get("used") else s2.get("reason", "not used") + ".") if s2 else "- Sentinel-2: not run."), "",
         "## What was damaged? (pre-event OSM objects on flooded pixels)",
         f"- Buildings: **{dm['buildings']['hit']} of {dm['buildings']['total']}**",
         f"- Road segments: **{dm['roads']['hit']} of {dm['roads']['total']}** · Bridges: **{dm['bridges']['hit']} of {dm['bridges']['total']}**", "",
         f"## Who is cut off? (road connection to nearest {c['destination']})",
         f"- **{len(cut)} settlements cut off**: " + (", ".join(sorted({r['name'] for r in cut if r['name']})) or "none") + ".",
         f"- {len(longer)} reachable only by a longer route; {c['counts'].get('connected', 0)} still connected; {c['counts'].get('not connected before', 0)} had no mapped road link even before the flood.", ""]
    if s.get("debris_rule"):
        dr = s["debris_rule"]; dd = dr["damage"]
        L += ["## Debris (radar + Sentinel-2)",
              f"- The AI model maps floodwater only. Debris = radar change (low confidence) plus Sentinel-2 vegetated→barren change where clear, on the valley floor: **{dr['km2']} km²** in the corridor.",
              f"- On it: buildings {dd['buildings']['hit']} of {dd['buildings']['total']}, road segments {dd['roads']['hit']} of {dd['roads']['total']}, bridges {dd['bridges']['hit']} of {dd['bridges']['total']}; "
              f"settlements cut off if those roads are blocked: {dr['cutoff'].get('CUT OFF', 0)}."]
        if "both_km2" in dr:
            L += [f"- Confidence: radar change {dr['radar_km2']} km², Sentinel-2 vegetated→barren {dr['optical_km2']} km²; **both agree on {dr['both_km2']} km²** (medium confidence)."]
        L += [""]
    if rz and rz["settlements"]:
        L += ["## Rescue priorities (cut-off settlements, largest first)",
              "- Buildings = pre-event OSM buildings nearest to the settlement. Landing site = flat, dry, open 30 × 30 m patch off the river channel (ICAO Annex 14 Vol II slope limits); crew must check obstacles."]
        for r in rz["settlements"][:8]:
            site = r["landing_sites"][0] if r["landing_sites"] else None
            L += [f"- **{r['name']}** ({r.get('place') or 'place'}): ≈{r['buildings']} buildings · cut off by {' + '.join(r['by'])} · "
                  + (f"nearest landing candidate {site['lat']}, {site['lon']} ({site['dist_km']} km)" if site else "no landing candidate found")]
        L += [""]
    if m:
        t = m.get("test_scores_unseen_events", {})
        ft = t.get("flood_tuned") or {"precision": t.get("flood_precision"), "recall": t.get("flood_recall"), "f1": t.get("flood_f1"), "iou": t.get("iou_flood")}
        L += ["## Model reliability",
              f"- U-Net trained on Kuro Siwo; on unseen test events: flood precision {r2(ft.get('precision'))}, recall {r2(ft.get('recall'))}, F1 {r2(ft.get('f1'))}, IoU {r2(ft.get('iou'))}"
              + (f" (flood threshold {round(m['flood_threshold'], 2)}, chosen on validation)." if m.get("flood_threshold") else "."),
              f"- Read as: about {round(100 * (ft.get('precision') or 0))} % of pixels it calls flooded are flooded, and it finds about {round(100 * (ft.get('recall') or 0))} % of flooded pixels.", ""]
    if s.get("runtime_s"):
        L += [f"*Answered in {int(s['runtime_s'] // 60)} min {int(s['runtime_s'] % 60)} s from raw satellite data.*", ""]
    L += local_summaries(s, c, rz)
    L += ["## Limitations (read before acting)",
          "- Sentinel-1 revisits every 6–12 days: this maps what the satellite saw, not the moment of the flood, and cannot warn in advance.",
          "- Steep Himalayan slopes cause radar layover/shadow; narrow gorges and debris under forest can be missed.",
          "- OSM completeness varies; unmapped buildings and roads cannot be counted. Damage = 'on a flooded/debris pixel', not structural damage; roads are cut only on the stretches that touch one.",
          "- Floodwater more than 15 m above the nearest mapped drainage is excluded (HAND rule, Twele et al. 2016); flooding fed by unmapped streams can be missed. Debris is not height-limited.",
          "- Educational prototype — verify on the ground before operational use.", "",
          "*" + " ".join(ATTRIB) + "*"]
    md = "\n".join(L)
    (d / "sitrep.md").write_text(md, encoding="utf-8")
    body = "".join(f"<h2>{html.escape(x[3:])}</h2>" if x.startswith("## ") else f"<h1>{html.escape(x[2:])}</h1>" if x.startswith("# ")
                   else f"<li>{html.escape(x[2:]).replace('**', '')}</li>" if x.startswith("- ") else f"<p>{html.escape(x).replace('*', '')}</p>" if x else "" for x in L)
    (d / "sitrep.html").write_text(f"<!doctype html><meta charset=utf-8><title>Sitrep {name}</title><style>body{{font:14px/1.45 system-ui;max-width:780px;margin:24px auto;color:#111}}h1{{font-size:20px}}h2{{font-size:15px;margin:14px 0 4px}}li{{margin:2px 0}}p{{font-size:12px;color:#444}}</style>{body}", encoding="utf-8")
    return md


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True)
    print(build(ap.parse_args().name))
