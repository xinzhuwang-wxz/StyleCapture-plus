# Style Party pose sprites

Four characters in four poses each, derived from the pose pack supplied by the
project owner on 2026-07-26 (`像素小人动作包/`, 16 × 1024×1536 RGBA PNGs).

The source pack is ~36 MB and is deliberately **not** committed; only these
trimmed 360px-tall sprites are. To regenerate them, put the original pack back
at the repository root and run:

    uv run python scripts/pixel_pose_cutout.py

The character/pose mapping lives in `POSE_PACK` in that script — it is the one
piece of human judgement in the pipeline and is recorded explicitly rather than
guessed at runtime.

| Output | Source file | SHA-256 of source |
| --- | --- | --- |
| `ash/idle.png` | `a0aed68a-4242-4b57-bad8-003c0bc21530.png` | `4aee5775ad2d5cea35207e8d7b818082a8b11ea8a978d3e5a0b390f39873edf1` |\n| `ash/wave.png` | `b10a7daf-32f1-4c5c-8b2f-e6538e93c1af.png` | `262fd1fe53bd2ec4194d430eaf42bab12c25a964a6310230f7738a2e78e58dc7` |\n| `ash/cheer.png` | `9312aa09-e19c-48ab-870f-142f0c05074a.png` | `16e298e30e50ad0906e15e1cb41760c7a96c3b1d9a48afae697b570390f26072` |\n| `ash/walk.png` | `1006868d-0494-47b6-9b1f-26a9cc50484d.png` | `2dcbb8360d426d4e56e34445b770c057ff9fa7083a1a8f1f23e6e7b7c3686e2d` |\n| `cargo/idle.png` | `f8ba107d-26a4-429a-ad43-9f962035593c.png` | `094116cb9808564eef7b1925e6f6a771c73786a5a90f13dbd684ffbf66b84604` |\n| `cargo/wave.png` | `1ab196cf-e791-4a38-89b8-bd5e144eb0a8.png` | `68ad548a7880c44d551d479d5893b94a1d99660113f6b1d63c5ac36f4523f2cd` |\n| `cargo/cheer.png` | `434bed2d-172d-46d1-a587-03e50eaef99e.png` | `35bcda50c3fab9f8aae9595f9b32ad8aa3e17afa27c75e872e0d733645b987d4` |\n| `cargo/walk.png` | `462c384d-9e99-417e-b56b-031c8226b4e8.png` | `40bc51be6fc85f2fb58fc5bad9d7cb5268c95d321fd56d26d7248eebdeb7f7f2` |\n| `linen/idle.png` | `f4c7ffba-b631-4024-948a-44c470450c8f.png` | `b0eb74a6a965c45f308a359477269c48974fd758686425f8df74770baa451ce8` |\n| `linen/wave.png` | `212afffa-5fe3-4921-8401-14e52e8479d1.png` | `a8037d4031979fe29f967a1f47ea77344a80da0eda0eaaefb4ec18b53d1ba97c` |\n| `linen/cheer.png` | `a04d3745-a9dd-4684-ae37-b415edbc06de.png` | `3d6dfcf1b28062a51556a001bc20dff2f7c283860a1c245162ad7d17c43c416d` |\n| `linen/walk.png` | `91391638-f023-48bf-9a9c-02a3100869b6.png` | `a7fa224026236808071e9248c9ce83fce78c2c61e695ad2c196b5fc74ebe22c1` |\n| `jersey/idle.png` | `79442189-e9ca-46c4-8d65-12944b75a62b.png` | `45395a84f17e3492e6420f3e33d884fae168b3e4149e8ea3c6590205a1c4b976` |\n| `jersey/wave.png` | `f720e68c-0cf1-49d1-a77e-8cc5ff94107d.png` | `f59cd2c5da431d3454008f501162c6adb3345afab78e7099fe80b7d3ed742fd5` |\n| `jersey/cheer.png` | `3735c1e1-4d82-4ae6-bdfe-ca4581781ae9.png` | `ddb58b54823edd2a39643c84bf8615b605ab4efd0b83029598e0c1371071197d` |\n| `jersey/walk.png` | `d89a5a6b-55bc-452c-b145-366b26debc60.png` | `8a9e0a21b5643e5606260df7e11360aac99a5f3d2d6a9d48ebef0263d06a0658` |

Poses are used only as the runtime's discrete animation states (idle / walk /
cheer / wave). The procedural rig in `world/characterRig.ts` animates between
them.
