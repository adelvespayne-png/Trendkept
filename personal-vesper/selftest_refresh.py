"""An install made before the map was filled in has to be able to catch up.

The seed only ever applies to a map file that doesn't exist yet, so the
laptop that installed Vesper last week is stuck with the thin starting map
it was born with. `refresh_from_seed` is the way out, and it has exactly two
jobs it must not get wrong:

  * bring in everything the new seed has;
  * keep every node the owner added themselves, and lose the stale lines
    from the older seed rather than showing both wordings at once.

The old 107-node seed is written out here rather than read from git, so the
test still means something once that commit is far behind us.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.mapstore import (PRIVATE_SEED, RESCUE_ID, SEED,  # noqa: E402
                            MapStore, _is_mine, current_seed)

# The shape of the seed that shipped before this one: the ids that went
# away (My trading was `mk*`, Personal was `me*`, the log was `log1..5`).
RETIRED = ["log1", "log2", "log3", "log4", "log5",
           "me", "me1", "me2", "me3",
           "mk", "mk0", "mk1", "mk1a", "mk1b", "mk1c",
           "mk2", "mk2a", "mk2b", "mk2c", "mk3", "mk3a", "mk3b",
           "mk4", "mk4a", "mk4b", "mk4c", "mk4d",
           "mk5", "mk5a", "mk5b", "mk5c", "mk6", "mk6a", "mk7"]


def old_map() -> dict:
    """A map roughly as an early install has it: retired ids under root."""
    nodes = {"root": {"id": "root", "t": "Vesper", "p": None, "done": False}}
    for nid in RETIRED:
        parent = "root" if len(nid) <= 3 else nid[:3]
        nodes[nid] = {"id": nid, "t": f"old wording for {nid}",
                      "p": parent if parent in RETIRED or parent == "root"
                      else "root", "done": False}
    # A handful of ids the new seed still uses, with the OLD text on them.
    nodes["prod1"] = {"id": "prod1", "t": "Engine & rules",
                      "p": "root", "done": False}
    nodes["prod1b"] = {"id": "prod1b", "t": "Stop goes in with the entry",
                       "p": "prod1", "done": False}
    return {"nodes": nodes, "links": [["mk4", "mk5"]]}


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


def main() -> int:
    bad = 0
    tmp = Path(tempfile.mkdtemp())

    # -- 1. an old install catches up, keeping the owner's own work --------
    path = tmp / "map.json"
    data = old_map()
    data["nodes"]["nab12cd9"] = {"id": "nab12cd9", "t": "AAPL — my own note",
                                 "p": "mk2", "done": False}
    data["nodes"]["nzz98ab7"] = {"id": "nzz98ab7", "t": "under my own note",
                                 "p": "nab12cd9", "done": False}
    data["links"].append(["nab12cd9", "mk2"])
    path.write_text(json.dumps(data), encoding="utf-8")

    store = MapStore(path)
    added, kept = store.refresh_from_seed()
    n = store.nodes()
    print(f"refresh: {added} added, {kept} of the owner's kept "
          f"-> {len(n)} nodes")

    bad += not check("every seed node is present",
                     all(k in n for k in current_seed()["nodes"]),
                     f"missing {sorted(set(current_seed()['nodes']) - set(n))[:5]}")
    bad += not check("the owner's own nodes survived",
                     "nab12cd9" in n and "nzz98ab7" in n)
    bad += not check("kept count is exactly the owner's two", kept == 2,
                     f"kept={kept}")
    bad += not check("their child still hangs off their parent",
                     n.get("nzz98ab7", {}).get("p") == "nab12cd9")
    bad += not check("a node whose parent retired is re-hung, not dropped",
                     n.get("nab12cd9", {}).get("p") == RESCUE_ID,
                     f"parent={n.get('nab12cd9', {}).get('p')}")
    # The limb ring must be exactly the seed's limbs — no more. Taken from
    # the seed rather than written out, so it holds whether or not the
    # private Health limb is on this machine.
    seed_limbs = sorted(v["t"] for v in current_seed()["nodes"].values()
                        if v["p"] == "root")
    bad += not check("and NOT onto the limb ring beside Trendkept",
                     sorted(v["t"] for v in n.values() if v["p"] == "root")
                     == seed_limbs,
                     str([v["t"] for v in n.values() if v["p"] == "root"]))
    bad += not check("the rescue box sits under Personal",
                     n.get(RESCUE_ID, {}).get("p") == "pr",
                     str(n.get(RESCUE_ID)))
    bad += not check("retired ids are gone",
                     not any(r in n for r in RETIRED),
                     f"still there: {[r for r in RETIRED if r in n][:5]}")
    bad += not check("stale wording was replaced, not kept",
                     n["prod1b"]["t"] == SEED["nodes"]["prod1b"]["t"],
                     n["prod1b"]["t"])
    bad += not check("a link between two retired nodes went with them",
                     not any(list(p) == ["mk4", "mk5"] for p in store.data["links"]))
    bad += not check("a link the owner made to a retired node also went",
                     not any(list(p) == ["nab12cd9", "mk2"]
                             for p in store.data["links"]))
    bad += not check("the old map was backed up",
                     path.with_suffix(".json.bak").is_file())

    # -- 2. it is safe to run again, and again ----------------------------
    # The rescue box holds the owner's nodes, so it has to count as theirs
    # and survive the next refresh. When its id was seed-shaped the second
    # run swept it away and silently moved its children somewhere else.
    sizes, parents = [len(store.nodes())], [dict(store.nodes())["nab12cd9"]["p"]]
    for _ in range(2):
        again_added, again_kept = store.refresh_from_seed()
        sizes.append(len(store.nodes()))
        parents.append(store.nodes()["nab12cd9"]["p"])
    bad += not check("running it again adds nothing", again_added == 0,
                     f"added={again_added}")
    bad += not check("the map stops changing size", len(set(sizes)) == 1,
                     str(sizes))
    bad += not check("and rescued nodes stay where they were put",
                     len(set(parents)) == 1, str(parents))

    # -- 2b. a node the owner hung at the root stays at the root ----------
    p3 = tmp / "atroot.json"
    d3 = old_map()
    d3["nodes"]["nmyownlimb"] = {"id": "nmyownlimb", "t": "a limb I made",
                                 "p": "root", "done": False}
    p3.write_text(json.dumps(d3), encoding="utf-8")
    s3 = MapStore(p3)
    s3.refresh_from_seed()
    bad += not check("a limb the owner made themselves is left at the root",
                     s3.nodes()["nmyownlimb"]["p"] == "root",
                     s3.nodes()["nmyownlimb"]["p"])

    # -- 3. a map the owner has really used keeps all of it ---------------
    p2 = tmp / "used.json"
    d2 = current_seed()
    for i, nid in enumerate(["nq1w2e3r", "nq1w2e3r4", "na9b8c7d"]):
        d2["nodes"][nid] = {"id": nid, "t": f"mine {i}", "p": "pr2",
                            "done": False}
    p2.write_text(json.dumps(d2), encoding="utf-8")
    s2 = MapStore(p2)
    a2, k2 = s2.refresh_from_seed()
    bad += not check("a current map keeps all three of the owner's",
                     k2 == 3 and a2 == 0, f"added={a2} kept={k2}")
    bad += not check("and they stayed where they were put",
                     all(s2.nodes()[x]["p"] == "pr2"
                         for x in ("nq1w2e3r", "na9b8c7d")))

    # -- 4. the discriminator itself --------------------------------------
    bad += not check("no seed id is mistaken for the owner's",
                     not any(_is_mine(k) for k in SEED["nodes"]),
                     str([k for k in SEED["nodes"] if _is_mine(k)][:5]))
    bad += not check("both uid generators are recognised",
                     _is_mine("nab12cd9") and _is_mine("nlz9q2k4c8ff"))

    # -- 5. the map is actually full now ----------------------------------
    kids: dict = {}
    for k, v in SEED["nodes"].items():
        kids.setdefault(v["p"], []).append(k)
    limbs = kids["root"]
    thin = [SEED["nodes"][x]["t"] for x in limbs
            if sum(len(kids.get(c, [])) for c in kids.get(x, [])) < 3]
    bad += not check("every limb has real depth under it", not thin, str(thin))
    leaves = [k for k in SEED["nodes"] if k not in kids]
    bad += not check("there are more leaves than headings",
                     len(leaves) > len(SEED["nodes"]) / 2,
                     f"{len(leaves)} leaves of {len(SEED['nodes'])}")

    # -- 6. the private limb: on this laptop, never in the repo -----------
    # The Health branch is git-ignored and ships in the download instead.
    # Its ids are seed-shaped, so if `refresh_from_seed` used the public
    # SEED alone it would sweep the whole branch off the owner's machine as
    # stale the first time they ran the tune-up.
    # Absent is CORRECT in a public clone, so this is not a failure either
    # way — it decides which set of expectations applies.
    have_private = PRIVATE_SEED.is_file()
    print("  ..   private seed: "
          + ("present — checking it survives a refresh"
             if have_private else "absent — this is a public clone, as designed"))
    bad += not check("the public seed never carries Health itself",
                     "Health" not in [v["t"] for v in SEED["nodes"].values()
                                      if v["p"] == "root"])
    if have_private:
        full = current_seed()["nodes"]
        limbs = [v["t"] for v in full.values() if v["p"] == "root"]
        bad += not check("with it, Health is a limb again",
                         "Health" in limbs, str(limbs))

        p6 = tmp / "withhealth.json"
        p6.write_text(json.dumps(current_seed()), encoding="utf-8")
        s6 = MapStore(p6)
        hl = [k for k, v in s6.nodes().items() if k.startswith("hl")]
        s6.refresh_from_seed()
        after = s6.nodes()
        bad += not check("a refresh KEEPS the whole Health branch",
                         all(k in after for k in hl),
                         f"lost {[k for k in hl if k not in after][:5]}")
        bad += not check("including the cross-links into it",
                         any(sorted(map(str, l)) == sorted(["hl3d", "nw3"])
                             for l in s6.data["links"]))

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
