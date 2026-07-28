# Task 2 iOS Dependency License And Privacy Audit

Source: `apps/ios/StyleCaptureJourney/Config/Package.resolved`.

| Identity | Version | Revision | License | Privacy manifest impact |
|---|---:|---|---|---|
| `combine-schedulers` | `1.2.0` | `dcccb979a2183b8df3334237e3dc1ae2b4116a86` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `grdb.swift` | `7.11.1` | `b83108d10f42680d78f23fe4d4d80fc88dab3212` | MIT | Ships `GRDB/PrivacyInfo.xcprivacy`; it declares no tracking, collected-data types, or required-reason API categories. |
| `nuke` | `13.0.6` | `63a8fcbd6621340a2410bc3e9575ac97058615f4` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `openapikit` | `6.2.0` | `57b6318128e3f901c93f4fbf98d1c1464ec168d3` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-algorithms` | `1.2.1` | `87e50f483c54e6efd60e885f7f5aa946cee68023` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-argument-parser` | `1.8.2` | `6a52f3251125d74daf04fcbd5e6f08a75d074382` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-case-paths` | `1.9.1` | `794f4b0a9cf32042592388d014f6a1ea987d323a` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-clocks` | `1.1.0` | `72d749bf341b78851203066ab421869b783ec42a` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-collections` | `1.6.0` | `a0cb0954ecb21e4e31b0070e6ed5674e8556685a` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-composable-architecture` | `1.26.1` | `ead11e04e5011c437722c1990d22f80d87056978` | MIT | Ships `Sources/ComposableArchitecture/Resources/PrivacyInfo.xcprivacy` and declares `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1`. |
| `swift-concurrency-extras` | `1.4.1` | `5fa253428866f2360c3754e88537f700ed2656b5` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-custom-dump` | `1.6.1` | `a8cd6c976f335ed361dcecddb0dc39ebda51bc3e` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-dependencies` | `1.14.1` | `8dc1fbf2f6255a73dec53b4648164884898db4c5` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-http-types` | `1.6.0` | `db774a277f60063a32d854f2980299caf06da041` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-identified-collections` | `1.1.1` | `322d9ffeeba85c9f7c4984b39422ec7cc3c56597` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-navigation` | `2.10.3` | `fad75807c596fecd724b0fc81cd61c94008faad4` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-numerics` | `1.1.1` | `0c0290ff6b24942dadb83a929ffaaa1481df04a2` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-openapi-generator` | `1.13.0` | `af9a2a1f5dcfb00a278d4bb29c6d75080932e99e` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-openapi-runtime` | `1.11.0` | `f039fa6d6338aab5164f3d1be16281524c9a8f89` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-openapi-urlsession` | `1.1.0` | `6fac6f7c428d5feea2639b5f5c8b06ddfb79434b` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-perception` | `2.0.11` | `de219a1cf34e958134e75a9ebb134cf09bf52fc6` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `swift-sharing` | `2.9.1` | `8244fe63bf43e58188ab13851ad693eecf6a9e90` | MIT | Ships `swift-sharing/Sources/Sharing/PrivacyInfo.xcprivacy`; declares `NSPrivacyAccessedAPICategoryFileTimestamp` / `C617.1` and `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1`. |
| `swift-syntax` | `603.0.2` | `79e4b74a295b6eb74a8b585e3a39d29e70c1dbd1` | Apache-2.0 | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `xctest-dynamic-overlay` | `1.11.0` | `8f6abcf4c8950e2679d5b2fee4ca284fd7c34886` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |
| `yams` | `6.2.2` | `a27b21e0c81c5bf42049b897a62aaf387e80f279` | MIT | No SDK privacy manifest found/required for this source package at Task 2; app manifest declares no tracking or collected data. |

P0/P1 blocker: none identified in resolved SwiftPM packages.

SDK privacy manifest correction (Task 3 release audit): the exact `Package.resolved` revisions were inspected in `.build/ios-task3/SourcePackages/checkouts`. Three source packages contain manifests: GRDB, swift-composable-architecture, and swift-sharing, as recorded above. Their package manifests declare no tracking or collected-data types. The repository validator can re-check the cached files with `python3 scripts/check_ios_privacy_manifest.py --source-packages .build/ios-task3/SourcePackages`. Final merged-archive inspection remains intentionally unverified until a signed archive is produced on an authorized Apple build host.
