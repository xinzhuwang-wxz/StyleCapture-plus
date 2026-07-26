# Style Party pose sprites

Seven characters derived from two pose packs supplied by the project owner on
2026-07-26: `像素小人动作包/` (16 files) and `新的像素小人动作包/` (11 files,
on-site crew and visitors). Most have four poses; `visitor-skirt` has three and
falls back to idle for walking.

The source packs total ~70 MB and are deliberately **not** committed; only these
trimmed 360px-tall sprites are. To regenerate them, put the original packs back
at the repository root and run:

    uv run python scripts/pixel_pose_cutout.py

The character/pose mapping lives in `POSE_PACK` in that script — it is the one
piece of human judgement in the pipeline and is recorded explicitly rather than
guessed at runtime.

| Output | Source file | SHA-256 of source |
| --- | --- | --- |
| `ash/idle.png` | `a0aed68a-4242-4b57-bad8-003c0bc21530.png` | `4aee5775ad2d5cea35207e8d7b818082a8b11ea8a978d3e5a0b390f39873edf1` |
| `ash/wave.png` | `b10a7daf-32f1-4c5c-8b2f-e6538e93c1af.png` | `262fd1fe53bd2ec4194d430eaf42bab12c25a964a6310230f7738a2e78e58dc7` |
| `ash/cheer.png` | `9312aa09-e19c-48ab-870f-142f0c05074a.png` | `16e298e30e50ad0906e15e1cb41760c7a96c3b1d9a48afae697b570390f26072` |
| `ash/walk.png` | `1006868d-0494-47b6-9b1f-26a9cc50484d.png` | `2dcbb8360d426d4e56e34445b770c057ff9fa7083a1a8f1f23e6e7b7c3686e2d` |
| `cargo/idle.png` | `f8ba107d-26a4-429a-ad43-9f962035593c.png` | `094116cb9808564eef7b1925e6f6a771c73786a5a90f13dbd684ffbf66b84604` |
| `cargo/wave.png` | `1ab196cf-e791-4a38-89b8-bd5e144eb0a8.png` | `68ad548a7880c44d551d479d5893b94a1d99660113f6b1d63c5ac36f4523f2cd` |
| `cargo/cheer.png` | `434bed2d-172d-46d1-a587-03e50eaef99e.png` | `35bcda50c3fab9f8aae9595f9b32ad8aa3e17afa27c75e872e0d733645b987d4` |
| `cargo/walk.png` | `462c384d-9e99-417e-b56b-031c8226b4e8.png` | `40bc51be6fc85f2fb58fc5bad9d7cb5268c95d321fd56d26d7248eebdeb7f7f2` |
| `linen/idle.png` | `f4c7ffba-b631-4024-948a-44c470450c8f.png` | `b0eb74a6a965c45f308a359477269c48974fd758686425f8df74770baa451ce8` |
| `linen/wave.png` | `212afffa-5fe3-4921-8401-14e52e8479d1.png` | `a8037d4031979fe29f967a1f47ea77344a80da0eda0eaaefb4ec18b53d1ba97c` |
| `linen/cheer.png` | `a04d3745-a9dd-4684-ae37-b415edbc06de.png` | `3d6dfcf1b28062a51556a001bc20dff2f7c283860a1c245162ad7d17c43c416d` |
| `linen/walk.png` | `91391638-f023-48bf-9a9c-02a3100869b6.png` | `a7fa224026236808071e9248c9ce83fce78c2c61e695ad2c196b5fc74ebe22c1` |
| `jersey/idle.png` | `79442189-e9ca-46c4-8d65-12944b75a62b.png` | `45395a84f17e3492e6420f3e33d884fae168b3e4149e8ea3c6590205a1c4b976` |
| `jersey/wave.png` | `f720e68c-0cf1-49d1-a77e-8cc5ff94107d.png` | `f59cd2c5da431d3454008f501162c6adb3345afab78e7099fe80b7d3ed742fd5` |
| `jersey/cheer.png` | `3735c1e1-4d82-4ae6-bdfe-ca4581781ae9.png` | `ddb58b54823edd2a39643c84bf8615b605ab4efd0b83029598e0c1371071197d` |
| `jersey/walk.png` | `d89a5a6b-55bc-452c-b145-366b26debc60.png` | `8a9e0a21b5643e5606260df7e11360aac99a5f3d2d6a9d48ebef0263d06a0658` |
| `crew-wide/idle.png` | `ad9c2950-3490-48b9-a1bd-26e6d980b832.png` | `96560f97513301e489d5b61a05f66ee037d61bbd795dc7acb889fdb2c3abe754` |
| `crew-wide/wave.png` | `18dd2303-1a5b-417d-a511-e28780475c80.png` | `bac53b8ba31f38ea67a439d8e8fbb3ccfafea532116d53bfff0ed2ebc539b260` |
| `crew-wide/cheer.png` | `87a8db74-eaed-48de-937b-908e05b72076.png` | `81cd3bc4ec11c22dda401e5fe0e3b778d3e2baf09e5805a2524f78f4631d6e5e` |
| `crew-wide/walk.png` | `348630ec-cf6d-4c9f-a4cb-c60956b279c1.png` | `b90c8f8228606ca17ae8b4ed59b826087702686c35025a276c4e44e89a27e061` |
| `crew-glasses/idle.png` | `43467758-04a5-4de2-9d70-1095f8440f97.png` | `f7f4cdfac6c23e99422eddfc48a0ff80b3d1b1c60dd15fd95d311cfbd0aa7dac` |
| `crew-glasses/wave.png` | `6fda1ec2-ef4f-4c97-b4b0-cecba4112c06(1).png` | `086ceaf967d009489c90ae1749d523ea0c1b91c81c3a2b6936813b76b72872c3` |
| `crew-glasses/cheer.png` | `fcdd2eb9-e69e-4438-9292-c2211c6b8c11.png` | `7dbcf0c90a6f8439dbc0ba119d63b42ad85b09399094898d44b0d07e6d97e959` |
| `crew-glasses/walk.png` | `6fda1ec2-ef4f-4c97-b4b0-cecba4112c06(1)(1).png` | `65357f0dec6ef0814afb6b7d546ab590955a97d8bf045b2e52fb6818471d312b` |
| `visitor-skirt/idle.png` | `a3310a4c-6834-4758-89fb-a30365cd163d.png` | `fd66c710ef4f01f85c80f3767c15e77dd03d80b7c269484fdaaa35d9e6015e71` |
| `visitor-skirt/wave.png` | `37c20763-5bfb-4eca-8e44-f8bb9cd769ba - 副本 (2).png` | `4ef8a2365085b9b37a035337d72914f4892bf8a596649d7cfae2590eb67fd541` |
| `visitor-skirt/cheer.png` | `37c20763-5bfb-4eca-8e44-f8bb9cd769ba.png` | `04eabea4482645fd272d012c7c5fda8c4216261798df14aa4612eb289f8f99b8` |

Poses are used only as the runtime's discrete animation states (idle / walk /
cheer / wave). The procedural rig in `world/characterRig.ts` animates between
them.
