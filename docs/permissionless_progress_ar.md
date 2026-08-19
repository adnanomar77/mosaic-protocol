# MOSAIC Permissionless Progress Report

## الحالة الحالية

انتقل MOSAIC من نواة permissioned pilot إلى تنفيذ أوسع يحتوي على lifecycle للـstake، bond قابل للتحقق، withdrawal delay، slashing evidence، randomness commit-reveal، اختيار لجان مربوطًا بـbeacon، حدود شبكة عامة، AvailabilityCertificate، deterministic execution kernel، ExecutionBinding، schema-versioned WAL، snapshots، migration، bounded model checking M1–M8، واختبارات testnet متعددة العمليات.

هذا التقرير **مرحلي** وليس إعلان mainnet. بعض الطبقات أصبحت منفذة وقابلة للاختبار، بينما لا يزال بعضها reference implementation يحتاج backend اقتصاديًا وشبكة WAN ومراجعة مستقلة.

## ما تم تنفيذه واختباره

| الطبقة | التنفيذ الحالي | دليل الاختبار |
|---|---|---|
| Stake lifecycle | `StakeBond` موقّع، تحقق owner/amount، withdrawal delay، `WithdrawalReceipt` | اختبارات membership الجديدة وsuite الكامل |
| Sybil penalty | `SlashEvidence` deterministic، تخفيض stake، jail عند التصفير، منع replay | اختبارات slashing |
| Randomness | commit-reveal، فتح commitment، quorum reveal weight، فصل epoch، beacon-bound committee proof | اختبارات randomness |
| Public network hardening | frame timeout، connect timeout، per-peer buckets، connection cap، pending cap، exponential backoff | اختبارات network limits وbenchmarks |
| Availability | `AvailabilityAttestation` و`AvailabilityCertificate` بوزن quorum وتوقيع Ed25519 | اختبارات availability وM7 |
| Execution | bounded deterministic kernel (`SET`, `DELETE`, `ADD_INT`)، nonce، gas، state roots، atomic batch | اختبارات execution وM8 |
| Storage | schema v2، migration additive، snapshots، pruning، WAL FULL، integrity check | اختبارات storage upgrade وnetwork snapshots |
| Formalization | TLA+ abstraction أولية وbounded Python checker لـM1–M8 | `formal/mosaic_safety.tla` و`docs/mosaic_model_check.json` |

## نتائج testnet المحلية

شُغلت عمليات TCP مستقلة، لا threads داخل عقدة واحدة، مع WAL وعزل مفاتيح وتوقيعات Ed25519. النتائج الآتية ليست نتائج شبكة WAN عامة، لكنها أقوى من نموذج داخل الذاكرة.

| السيناريو | العقد | العمليات | p50 | p95 | النتيجة |
|---|---:|---:|---:|---:|---|
| healthy | 4 | 10/10 | 18.716661 ms | 20.156456 ms | صفر أخطاء |
| healthy | 10 | 20/20 | 61.758052 ms | 72.236053 ms | صفر أخطاء |
| drop + Byzantine | 7 | 30/30 | 36.749191 ms | 49.126423 ms | 5% drop، 2 ms delay، Byzantine واحد، صفر أخطاء |
| adaptive Byzantine | 7 | 20/20 | 42.456362 ms | 52.029440 ms | عقدتان Byzantine من أصل 7، 3% drop، صفر أخطاء |

في adaptive Byzantine سُجلت تعارضات متوقعة بسبب توقيعات `ACCEPT/ABANDON` المتعارضة، ولم تتحول إلى أخطاء تشغيلية أو إغلاقين متعارضين. هذه نتيجة schedule محدد وليست برهانًا على كل adversarial schedules.

## المقارنة الرسمية وحدودها

تشغيل `run_unified_comparison.py` ينتج controlled abstractions لنماذج HotStuff-style وNarwhal/Tusk-style وSui Lutris-style، وليس implementations الرسمية. لذلك لا تستخدم أرقام هذا الملف لإثبات تفوق MOSAIC. المرجع الرسمي لـlibhotstuff يذكر أنه prototype implementation مرتبطة بتقييم HotStuff، بينما يوفّر مستودع Narwhal/Tusk Rust وscripts benchmark. [1] [2]

توثيق Sui يذكر controlled results لـMysticeti، منها نحو 0.5 ثانية commitment و200,000 TPS في إعداد الاختبار، ويصرح أن هذه ليست production metrics. [3] ورقة Sui Lutris تذكر أقل من 0.5 ثانية عند 5,000 certificates/s، أي 150k ops/s مع transaction blocks، ضمن إعدادها الخاص. [4] لا يجوز مقارنة هذه الأرقام بنتائج MOSAIC المحلية حتى تُشغّل binary baselines حقيقية بنفس workload والعتاد والشبكة وتعريف finality.

## ما لا يزال يمنع إعلان permissionless mainnet

رغم التقدم، فإن `StakeBond` الحالي كائن protocol قابل للتحقق وليس بعد ledger اقتصاديًا حقيقيًا يملك custody وfee market وrewards وslashing settlement عبر أصول فعلية. كما أن commit-reveal beacon يحتاج incentive ضد عدم reveal، fallback آمنًا، وتدويرًا فعليًا للجان داخل epoch transition proof؛ لا يكفي وجود class محلي وحده.

كذلك AvailabilityCertificate يثبت attestations من validators، لكنه ليس بعد erasure-coded availability network مع repair وsampling ومقاومة data withholding. وexecution kernel ليس VM عقود ذكية عامة؛ هو instruction set محدود أُنشئ أولًا لإثبات deterministic state transitions بأمان.

ما زالت مطلوبة شبكة WAN عامة، churn واختبارات طويلة المدة، power-loss وdisk-full، formal checker مستقل فعليًا، مراجعة cryptographic/network/economic، binary baselines حقيقية، governance للترقيات، وآلية تشغيل permissionless كاملة. لذلك التصنيف الحالي هو **advanced permissioned reference network / pre-public-testnet**, وليس mainnet عامة.

## References

[1]: https://github.com/hot-stuff/libhotstuff — libhotstuff official repository and prototype notes.

[2]: https://github.com/MystenLabs/narwhal — Narwhal/Tusk official repository and benchmark README.

[3]: https://docs.sui.io/develop/sui-architecture/consensus — Sui consensus and Mysticeti documentation.

[4]: https://arxiv.org/abs/2310.18042 — Sui Lutris paper and reported controlled results.
