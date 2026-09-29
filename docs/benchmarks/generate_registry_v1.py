#!/usr/bin/env python3
"""Generate docs/benchmarks/BENCHMARK_TASK_REGISTRY_V1.json.

Enumerates:
  - NYU CTF Bench test split (200, official frozen test set)  -> split=broad
  - NYU CTF Bench dev split  (57, from main-branch index)     -> split=diagnostic_dev_pool
  - Cybench local-verified tasks (43, metadata extracted from local clone):
       admission batch-1 members (10) + reserve (31) + excluded-by-protocol (2)
                                                               -> split=diagnostic_dev_pool
  - Cybench 9 GlacierCTF tasks listed upstream but absent     -> split=unavailable
  - Holdout Tier A pools (CSAW 2024/2025, CVE-Bench) + Tier B mechanism
No solutions are read; only metadata.json fields and directory names.
"""
import json, os, glob, re
from pathlib import Path

CYBENCH_REPO = str(Path(__file__).resolve().parents[3] / "cybench_repo")

NYU_TEST_200 = """2017f-rev-48_bit_yeet_lab 2017f-rev-rusty_road 2017f-rev-rabbithole 2017f-cry-ecxor 2017f-cry-lupin
2017f-for-thoroughlystripped 2017f-pwn-humm_sch_t 2017q-rev-bananascript 2017q-rev-tablez 2017q-rev-realism
2017q-rev-grumpcheck 2017q-rev-prophecy 2017q-rev-gopherz 2017q-cry-another_xor 2017q-cry-baby_crypt
2017q-cry-almost_xor 2017q-for-missed_registration 2017q-for-best_router 2017q-msc-cvv 2017q-msc-serial
2017q-web-littlequery 2017q-web-orangev2 2017q-web-orange 2017q-web-notmycupofcoffe 2017q-pwn-pilot
2017q-pwn-zone 2018f-rev-free_as_in_freedom 2018f-rev-bdos 2018f-rev-1nsayne 2018f-cry-asr4cr
2018f-cry-lost_mind 2018f-cry-distastrous_security_apparatus 2018f-msc-showdown 2018f-msc-leaked_flag
2018f-pwn-es1337 2018q-rev-a_walk_through_x86_part_2 2018q-rev-kvm 2018q-rev-a_walk_through_x86_part_1
2018q-cry-lowe 2018q-cry-collusion 2018q-cry-babycrypto 2018q-cry-flatcrypt 2018q-for-simple_recovery
2018q-for-whyos 2018q-msc-short_circuit 2018q-msc-bin_t  2018q-msc-algebra 2018q-pwn-shellpointcode
2018q-pwn-bigboy 2018q-pwn-get_it 2019f-rev-wrangly 2019f-rev-mystery_boi 2019f-rev-steady_counting
2019f-cry-macrypto 2019f-msc-alive 2019f-web-biometric 2019f-pwn-arevenge 2019q-rev-beleaf
2019q-rev-call_site 2019q-rev-gibberish_check 2019q-rev-halfpike 2019q-rev-wizkid 2019q-cry-des2bites
2019q-cry-brillouin 2019q-cry-count_on_me 2019q-cry-super_curve 2019q-cry-byte_me
2019q-pwn-pop_goes_the_printer 2019q-pwn-got_milk 2019q-pwn-popping_caps_2 2019q-pwn-popping_caps
2019q-pwn-small_boi 2019q-pwn-baby_boi 2019q-pwn-traveller 2020f-rev-rap 2020f-rev-brrr 2020f-rev-yeet
2020f-rev-sourcery 2020f-cry-eccentric 2020f-cry-hybrid2 2020f-cry-the_matrix 2020f-cry-jackpot
2020f-web-snailrace1 2020f-web-picgram 2020f-web-sharkfacts 2020f-pwn-darkunion1 2020q-rev-not_malware
2020q-rev-ezbreezy 2020q-rev-baby_mult 2020q-cry-authy 2020q-cry-difib 2020q-cry-perfect_secrecy
2020q-cry-adversarial 2020q-cry-smallsurp 2020q-cry-modus_operandi 2020q-pwn-thebardsfail
2020q-pwn-slithery 2020q-pwn-grid 2020q-pwn-feather 2020q-pwn-blox2 2020q-pwn-pwnvoltex
2020q-pwn-roppity 2021f-rev-maze 2021f-rev-sfc 2021f-cry-interoperable 2021f-cry-ibad
2021f-cry-collision_course 2021f-for-no_time_to_register 2021f-for-constela 2021f-msc-terminal_velocity
2021f-pwn-horrorscope 2021f-pwn-chatterbox 2021q-rev-ransomware 2021q-rev-macomal 2021q-rev-ncore
2021q-rev-checker 2021q-cry-bits 2021q-cry-gotta_decrypt_them_all 2021q-cry-crack_me
2021q-cry-rsa_pop_quiz 2021q-cry-ecc_pop_quiz 2021q-cry-forgery 2021q-for-lazy_leaks
2021q-msc-weak_password 2021q-msc-save_the_tristate 2021q-web-no_pass_needed 2021q-web-poem_collection
2021q-web-securinotes 2021q-web-gatekeeping 2021q-web-scp_terminal 2021q-pwn-krypto 2021q-pwn-alien_math
2021q-pwn-password_checker 2021q-pwn-haystack 2022f-rev-roulette 2022f-rev-parallel_vm
2022f-cry-open_ellipti_ph 2022f-cry-polly_crack_this 2022f-cry-m_ster_0f_prn9
2022f-cry-the_lengths_we_extend_ourselves 2022f-msc-farmlang 2022f-msc-embrey0_leak
2022f-msc-super_guesser_g_me 2022f-pwn-salt_server 2022f-pwn-cryptopwn 2022q-rev-dockreleakage
2022q-rev-game 2022q-rev-anyagacha 2022q-rev-the_big_bang 2022q-cry-beyond_quantum
2022q-cry-too_much_in_common 2022q-cry-gift_shop 2022q-cry-gotta_crack_them_all 2022q-cry-not_too_taxing
2022q-msc-quantum_leap 2022q-msc-ezmaze 2022q-msc-cattheflag 2022q-pwn-ezrop 2022q-pwn-unsafe_linking
2023f-rev-unvirtualization 2023f-rev-cell 2023f-rev-virtualization 2023f-cry-nervcenter
2023f-cry-textbook_rsa 2023f-cry-describeme 2023f-for-forensings 2023f-for-hypokrinesthai
2023f-for-floating_points 2023f-for-ancient_forensics 2023f-for-emoji 2023f-msc-pyjail
2023f-msc-vectors_machine 2023f-msc-urkel 2023f-msc-sigmaslogistics 2023f-web-shreeramquest
2023f-web-triathlon_or_sprint 2023f-pwn-virtualization_pwn 2023f-pwn-brainflop 2023q-rev-whataxor
2023q-rev-baby_s_first 2023q-rev-rox 2023q-rev-rebug_2 2023q-rev-baby_s_third 2023q-rev-rebug_1
2023q-cry-mental_poker 2023q-cry-circles 2023q-cry-lottery 2023q-for-br3akth3vau1t
2023q-for-1black0white 2023q-msc-android_dropper 2023q-msc-tradinggame 2023q-msc-linear_aggressor
2023q-web-cookie_injection 2023q-web-philanthropy 2023q-web-rainbow_notes 2023q-web-smug_dino
2023q-pwn-unlimited_subway 2023q-pwn-target_practice 2023q-pwn-puffin 2023q-pwn-my_first_pwnie""".split()

NYU_DEV = """2013f-cry-stfu 2013f-web-historypeats 2013q-cry-csawpad 2013q-cry-slurp 2013q-cry-onlythisprogram
2013q-msc-life 2013q-msc-networking_2 2013q-msc-networking_1 2013q-web-guess_harder 2013q-pwn-csaw_diary
2014f-rev-return_of_the_weiner 2014f-rev-odd 2014f-msc-pps 2014f-web-webroot 2014f-pwn-kernel
2014q-rev-aerosol_can 2014q-rev-weissman 2014q-web-silkgoat 2014q-pwn-ish 2014q-pwn-the_road_less_traveled
2016f-rev-palo_alto 2016f-cry-katy 2016f-cry-killer_cipher 2016f-for-pure_poetry 2016f-web-cloudb
2016f-web-seizure_cipher 2016f-pwn-detective 2016q-rev-rock 2016q-rev-deedeedee 2016q-cry-sleeping_guard
2016q-cry-broken_box 2016q-for-watchword 2016q-for-kill 2016q-for-yaar_haar_fiddle_dee_dee
2016q-for-clams_dont_dance 2016q-for-evidence_zip 2016q-msc-coinslot 2016q-msc-regexpire 2016q-web-i_got_id
2016q-web-mfw 2016q-pwn-warmup 2016q-pwn-tutorial 2016q-pwn-hungman 2015f-rev-wyvern2 2015f-for-mandiant
2015f-pwn-hipster 2015q-rev-ftp 2015q-rev-wyvern 2015q-cry-eps 2015q-cry-eps_part2
2015q-cry-bricks_of_gold 2015q-for-sharpturn 2015q-for-flash 2015q-for-pcapin 2015q-web-k_stairs
2015q-web-throwback 2015q-pwn-meme_shop""".split()

NYU_BATCH1 = {
    "2016f-pwn-detective", "2016q-pwn-hungman", "2014f-pwn-kernel", "2016q-pwn-warmup",
    "2016f-cry-killer_cipher", "2016q-cry-broken_box", "2015q-cry-eps_part2", "2013f-cry-stfu",
    "2014f-rev-odd", "2016f-rev-palo_alto", "2015f-rev-wyvern2",
    "2016q-web-mfw", "2013f-web-historypeats", "2016q-web-i_got_id",
    "2016q-for-yaar_haar_fiddle_dee_dee", "2015q-for-pcapin",
    "2016q-msc-regexpire", "2014f-msc-pps",
}

NYU_DEV_BROKEN = {
    "2015f-pwn-hipster": "issue #21: flag is placeholder flag{temp} — false-positive solves; repair or drop before any split",
    "2015q-web-k_stairs": "issue #18: flag typo (missing char) — fixed upstream, verify at bring-up",
}
NYU_TEST_FLAGGED = {
    "2021q-cry-crack_me": "issue #14 history: README once leaked flag; verify tag v20250206 copy",
    "2023q-web-cookie_injection": "issue #19: DNS name mismatch challenge.json vs compose; needs repair",
}

CAT_MAP = {"cry": "crypto", "rev": "reversing", "pwn": "pwn", "web": "web", "for": "forensics", "msc": "misc"}

CYBENCH_BATCH1 = {
    "noisy-crc", "ezmaze", "diffecient", "Permuted", "robust-cbc",
    "frog-waf", "LockTalk", "matrix-lab-2", "Data-Siege", "just-another-pickle-jail",
}
CYBENCH_EXCLUDED = {
    "chunky": "internet.necessary=true — excluded from offline anti-contamination protocol",
    "05-motp": "GPL license (removed from UK AISI port for same reason)",
}
CYBENCH_DIFF_DESC = {0: "very easy", 1: "easy", 2: "normal/medium", 3: "hard", 4: "expert", 5: "master"}

CYBENCH_MISSING_9 = [
    ("MissingBits", "crypto"), ("SLCG", "crypto"), ("WalkingToTheSeaSide", "crypto"),
    ("shuffled-aes", "crypto"), ("skilift", "misc"), ("avatar", "misc"),
    ("rpgo", "reversing"), ("sop", "reversing"), ("GlacierExchange", "web"),
]


def nyu_entry(tid, split, status, extra_note=""):
    year = tid[:4]; rnd = tid[4]; cat = CAT_MAP[tid[6:9]]
    notes = [f"CSAW {year} {'finals' if rnd=='f' else 'quals'}"]
    if tid in NYU_DEV_BROKEN: notes.append(NYU_DEV_BROKEN[tid])
    if tid in NYU_TEST_FLAGGED: notes.append(NYU_TEST_FLAGGED[tid])
    if extra_note: notes.append(extra_note)
    return {
        "task_id": f"nyuctf:{tid}",
        "benchmark": "nyuctf",
        "split": split,
        "category": cat,
        "difficulty": None,  # CTF points recorded in challenge.json; fill at bring-up
        "environment": "docker-compose via nyuctf package (llmctf/* images); compose flag per challenge.json",
        "evaluator": "harness-side exact-match flag vs challenge.json",
        "diagnostic_status": status,
        "source_version": "NYU_CTF_Bench tag v20250206 (index cross-checked against main branch 2026-09)",
        "contamination_risk": "high",
        "notes": "; ".join(notes),
    }


def cybench_entries():
    rows, seen = [], set()
    for root, dirs, files in os.walk(os.path.join(CYBENCH_REPO, "benchmark")):
        if "metadata.json" not in files: continue
        mp = os.path.join(root, "metadata.json")
        key = os.path.dirname(mp)
        if key in seen: continue
        seen.add(key)
        with open(mp) as f: m = json.load(f)
        rel = os.path.relpath(os.path.dirname(key), os.path.join(CYBENCH_REPO, "benchmark"))
        base = os.path.basename(os.path.dirname(key))  # task dir name (metadata.json lives in <task>/metadata/)
        name = re.sub(r"^\[[^\]]*\]\s*", "", base).replace(" ", "-")  # strip HTB "[Medium] " style tags
        cats = m.get("categories") or []
        cat = {"reverse": "reversing", "forensics": "forensics"}.get(cats[0], cats[0]) if cats else "unknown"
        has_target = bool(m.get("target_host"))
        env = ("docker service on shared network (target_host=%s) + files via init_script.sh" % m["target_host"]
               if has_target else "files only (no service); files via init_script.sh")
        internet = (m.get("internet") or {})
        notes = [f"source path: {rel}", f"subtasks: {len(m.get('subtasks', []))}",
                 f"difficulty {m['difficulty']} = {CYBENCH_DIFF_DESC.get(int(m['difficulty']), '?')}"]
        if internet.get("necessary"): notes.append("internet.necessary=true")
        elif internet.get("useful"): notes.append("internet.useful=true")
        status = "candidate_batch1" if name in CYBENCH_BATCH1 else "candidate_reserve"
        if name in CYBENCH_EXCLUDED: status = "excluded_protocol"
        rows.append({
            "task_id": f"cybench:{name}",
            "benchmark": "cybench",
            "split": "diagnostic_dev_pool",
            "category": cat,
            "difficulty": int(m["difficulty"]),
            "environment": env,
            "evaluator": "harness-side exact-match flag vs metadata.json final subtask answer; intermediate subtask answers reserved for research-side partial progress",
            "diagnostic_status": status,
            "source_version": "andyzorigin/cybench commit ca483c6 (2026-09-24, local clone; metadata only, solutions unread)",
            "contamination_risk": "high",
            "notes": "; ".join(notes),
        })
    # sanity: every batch1 task must be present exactly once
    names = [r["task_id"].split(":", 1)[1] for r in rows]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"cybench task_id collision: {dupes}"
    missing = CYBENCH_BATCH1 - set(names)
    assert not missing, f"batch1 cybench tasks missing from clone: {missing}"
    return rows


def main():
    tasks = []
    for tid in NYU_TEST_200:
        tasks.append(nyu_entry(tid, "broad", "fixed_broad_do_not_iterate",
                               "official frozen test set; run only at milestones"))
    for tid in NYU_DEV:
        status = "candidate_batch1" if tid in NYU_BATCH1 else "candidate_reserve"
        tasks.append(nyu_entry(tid, "diagnostic_dev_pool", status))
    rows = cybench_entries()
    tasks.extend(rows)
    for name, cat in CYBENCH_MISSING_9:
        tasks.append({
            "task_id": f"cybench:{name}",
            "benchmark": "cybench",
            "split": "unavailable",
            "category": cat,
            "difficulty": None,
            "environment": "n/a — listed in upstream task_list.txt but never committed (LosFuzzys absent from all 552 commits)",
            "evaluator": "n/a",
            "diagnostic_status": "excluded_missing_upstream",
            "source_version": "andyzorigin/cybench commit ca483c6; recover via 0ca/cybench-patched or UK AISI inspect_evals port if ever needed",
            "contamination_risk": "high",
            "notes": "upstream source dir is literally GlacierCTF2023_writeups (solutions public)",
        })

    # holdout Tier A pools + Tier B mechanism
    holdout = [
        {
            "task_id": "holdoutA:csaw-2024-quals-pool",
            "benchmark": "csaw-live-repack",
            "split": "holdout_sealed",
            "category": "mixed",
            "difficulty": "post-2023 CSAW (EnIGMA anchor: frontier 2024 models solved 2/21 of the 21-task subset)",
            "environment": "self-packaged from osirislab/CSAW-CTF-2024-quals into nyuctf format; hash-frozen at packaging",
            "evaluator": "harness-side exact-match flag",
            "diagnostic_status": "sealed_do_not_run",
            "source_version": "to be frozen at packaging time (expected ~21-40 tasks)",
            "contamination_risk": "medium (published after most current model cutoffs; writeups exist but sparse)",
            "notes": "Tier A sealed static holdout; run only after candidate-stable version freeze",
        },
        {
            "task_id": "holdoutA:csaw-2025-pool",
            "benchmark": "csaw-live-repack",
            "split": "holdout_sealed",
            "category": "mixed",
            "difficulty": "2025 CSAW (quals+finals), freshest static source",
            "environment": "self-packaged, hash-frozen at packaging",
            "evaluator": "harness-side exact-match flag",
            "diagnostic_status": "sealed_do_not_run",
            "source_version": "to be frozen at packaging time",
            "contamination_risk": "medium-low",
            "notes": "Tier A; pair with csaw-2024 pool",
        },
        {
            "task_id": "holdoutA:cve-bench-40",
            "benchmark": "cve-bench",
            "split": "holdout_sealed",
            "category": "web (40 real CVEs, zero-day setting, flag-based; SOTA ~30%)",
            "difficulty": "hard (best published 30% PenForge)",
            "environment": "docker per task; adapter-compatible",
            "evaluator": "flag submission (built-in)",
            "diagnostic_status": "sealed_do_not_run",
            "source_version": "UIUC CVE-Bench (ICML 2025); pin at bring-up",
            "contamination_risk": "medium (CVEs public, but exploit chain reconstruction still hard)",
            "notes": "Tier A web-exploitation axis complement",
        },
        {
            "task_id": "holdoutB:live-ctf-mechanism",
            "benchmark": "ctfusion-methodology",
            "split": "holdout_fresh_live",
            "category": "mixed (event-dependent)",
            "difficulty": "event-dependent (CTFusion live mean weight 39.6 vs NYU 31.6)",
            "environment": "CTFd-hosted live event via CTFusion-style MCP proxy (per-system submission limits, first-correct dedup, agent isolation)",
            "evaluator": "CTFd challenge checker via proxy",
            "diagnostic_status": "mechanism_only_no_tasks",
            "source_version": "kaist-hacking/CTFusion (arXiv 2605.11504); the 2025 176-task live set is now public and NOT reusable as holdout",
            "contamination_risk": "low (structurally: challenges unreleased at eval time)",
            "notes": "Tier B: the only 'fresh' evaluation; run when a suitable CTFd event with API access occurs",
        },
    ]
    tasks.extend(holdout)

    registry = {
        "registry_version": "V1",
        "created": "2026-09-29",
        "decision": {
            "primary_benchmark": "nyuctf",
            "diagnostic_source": "nyuctf dev split (2013-2016) + cybench (difficulty>=2, locally verified)",
            "development_source": "same pool, disjoint from diagnostic, target 15-24 tasks",
            "broad_benchmark": "nyuctf test split (200 tasks, tag v20250206 + local repair manifest)",
            "holdout": "Tier A sealed static (CSAW 2024/2025 repack + CVE-Bench-40) / Tier B fresh live (CTFusion methodology)",
            "selection_doc": "docs/benchmarks/BENCHMARK_SELECTION_V1.md",
        },
        "benchmark_status": [
            {"benchmark": "nyuctf", "role": "primary + broad", "verdict": "selected",
             "reason": "200-task official frozen test set; 6 categories incl. 39 pwn; tiny images, clean reset, framework-agnostic; frontier 59% (rising, unsaturated); 4+ independent harnesses exist"},
            {"benchmark": "cybench", "role": "diagnostic/dev pool only", "verdict": "selected_secondary",
             "reason": "best per-task difficulty labels + subtask/hints metadata; but 40 tasks, pwn=2, frontier-saturated (93-100%), severe contamination, 9 tasks missing upstream"},
            {"benchmark": "ctfusion", "role": "holdout mechanism (Tier B)", "verdict": "methodology_adopted",
             "reason": "not a task corpus; live-CTF streaming eval framework with contamination control"},
            {"benchmark": "cybergym", "verdict": "rejected",
             "reason": "not flag-CTF (differential sanitizer PoV); Level-1 near-saturated per authors; 240GB-10TB infra; flag signal misleading (any-crash != target repro)"},
            {"benchmark": "ctf-dojo", "verdict": "deferred (V2 dev-pool expansion)",
             "reason": "658 dockerized tasks, largest corpus, but 2025-08 release with thin freezing/integration info"},
            {"benchmark": "cve-bench", "verdict": "selected into holdout Tier A",
             "reason": "fresh-ish web CVE, flag-based, zero-day setting, SOTA 30%"},
            {"benchmark": "intercode-ctf", "verdict": "rejected (smoke test only)",
             "reason": "saturated (72% GPT-4 Turbo) + 14.1% measured answer leakage"},
            {"benchmark": "autopenbench", "verdict": "not selected (V1)",
             "reason": "multi-host pentest distribution, different axis from flag-jeopardy; milestone evaluator noted as good idea"},
            {"benchmark": "pentesteval", "verdict": "not selected (V1; re-evaluate V2)",
             "reason": "stage-level scoring aligns with project philosophy but needs second harness; not CTF"},
            {"benchmark": "cybergym-e2e", "verdict": "not selected",
             "reason": "patch/discovery lifecycle benchmark; off-axis for flag CRS"},
            {"benchmark": "caibench", "verdict": "not selected",
             "reason": "10k-instance meta-benchmark; too heavy to stand up for V1"},
            {"benchmark": "exploitgym", "verdict": "not selected (watch)",
             "reason": "898 real-vuln exploitation instances (2026-05); promising for a future exploitation track"},
        ],
        "counts": {},
        "tasks": tasks,
    }
    # counts
    from collections import Counter
    registry["counts"] = {
        "total": len(tasks),
        "by_split": dict(Counter(t["split"] for t in tasks)),
        "by_diagnostic_status": dict(Counter(t["diagnostic_status"] for t in tasks)),
    }
    out = Path(__file__).with_name("BENCHMARK_TASK_REGISTRY_V1.json")
    with open(out, "w") as f:
        json.dump(registry, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("nyuctf test:", len(NYU_TEST_200), "dev:", len(NYU_DEV),
          "batch1 dev:", len(NYU_BATCH1 & set(NYU_DEV)), "cybench:", len(rows),
          "holdout:", len(holdout), "TOTAL:", len(tasks))
    print("counts:", json.dumps(registry["counts"]))


if __name__ == "__main__":
    main()
