# MOSAIC Long-Run Testnet Rehearsal

شُغلت سبع عمليات daemon لمدة اختبارية على مضيف واحد، مع 120 عملية، عقدتين Byzantine (`w0`,`w1`)، قتل `w1` عند العملية 40 وإعادة تشغيله من SQLite WAL، و24 اتصال partial-frame لقياس مقاومة DoS. أُضيف سجل JSONL append-only hash-chained يتضمن بدء الشبكة، تحقق onboarding/beacon/availability gates، جدول Byzantine، kill/restart، وconfig-only upgrade candidate.

| المقياس | النتيجة |
|---|---:|
| العمليات المطلوبة | 120 |
| العمليات الناجحة | **120/120** |
| liveness ratio | **1.0** |
| safety errors غير المتوقعة | **0** |
| Byzantine validators | 2 من 7 |
| kill/restart | `w1` عند العملية 40، استعادة WAL ناجحة |
| p50 | 36.804089 ms |
| p95 | 233.559733 ms |
| bytes per successful operation | 184,916.02 تقريبًا، مع تفصيل sent/received حسب message type |
| partial frames المغلقة | 24 |
| event log | 8 أحداث، hash-chain verified |

النتيجة محفوظة في `testnet/artifacts/mosaic_testnet_long_final.json`، وسجل الأحداث النهائي في `testnet/events/testnet-0-final.jsonl`. conflicts الناتجة عن Byzantine بقيت evidence/protocol conflicts ولم تُصنف كأخطاء تشغيلية. هذه نتيجة قوية لـlocal multi-process rehearsal، لكنها لا تمثل WAN حقيقية أو validators مستقلين؛ لذلك لا تُرفع وحدها إلى public testnet.

تسجيل الترقية في هذه المرحلة هو `config-v2` بحالة `not_applied_to_consensus`. لم تُنفذ ترقية consensus صامتة؛ وهذا مقصود لأن upgrade العامة تحتاج governance window ومشغلين مستقلين وcompatibility proof.
