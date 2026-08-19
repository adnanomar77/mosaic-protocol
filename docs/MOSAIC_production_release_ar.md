# MOSAIC — تقرير اختبار الإصدار الإنتاجي والحكم النهائي

## الخلاصة التنفيذية

اكتملت في هذه الدورة بوابة اختبار إنتاجية موسعة لنواة MOSAIC. النتيجة الحالية ليست مجرد نموذج داخل الذاكرة: توجد عقد TCP مستقلة، gossip بلا جامع مركزي، تخزين SQLite WAL دائم، استعادة بعد إعادة التشغيل، عزل مفاتيح، TLS اختياري mTLS، حماية replay، rate limiting، عضوية موزونة، اختبارات تعارض وByzantine، واختبارات partition وfuzzing وmodel checking محدود.

الحكم الدقيق هو أن **MOSAIC قابل للتشغيل كشبكة validators ثابتة ومصرّح بها، ونجح في اختبارات الإنتاج المحلية المحددة أدناه**. لكنه لا يصح وصفه بعد بأنه بروتوكول permissionless مكتمل أو بديل عام جاهز للإنترنت المفتوح؛ ما زالت توجد التزامات هندسية وبحثية صريحة موثقة في نهاية هذا التقرير.

## بوابة الاختبار

أصبحت مجموعة الاختبارات الآلية تحتوي على **40 اختبارًا ناجحًا** بعد إضافة اختبارات restart/fuzzing وmodel checking إلى الاختبارات السابقة. كما نجح `compileall` لجميع حزم MOSAIC وbenchmarks وtests.

| المسار | النتيجة | الدلالة |
|---|---:|---|
| `pytest` الكامل | 40/40 | لا regression في البروتوكول والتخزين والأمان والعضوية والشبكة |
| model checking محدود | ناجح | 84 حالة و36,703 زوج quorums في فحص تقاطع النصاب، مع نجاح M2–M6 |
| crash/restart متعدد العمليات | ناجح | قتل عقدة فعلية أثناء submit ثم إعادتها من WAL واستكمال الحالة |
| partition ثم healing | ناجح | توقف liveness دون quorum ثم عودة الإغلاق بعد إعادة الاتصال |
| fuzzing مخصص للإطارات | ناجح | رسائل JSON ناقصة ومشوهة ومتنوعة لم تُسقط خادم العقدة |

نتيجة model checking **محدودة bounded** وليست برهانًا آليًا غير محدود في TLA+ أو Ivy أو Coq أو Lean. لذلك تُستخدم كاختبار قابل لإعادة الإنتاج للـreference implementation، لا كبديل عن البرهان الرسمي الكامل.

## نتائج الشبكة الموزعة

شُغّلت العقد كعمليات TCP مستقلة، مع مفاتيح خاصة محلية فقط، وWAL وأمان الشبكة مفعّلين. كل عملية submit تُغلق عبر receipt gossip، ولا يوجد leader أو collector مركزي في مسار الإغلاق.

| السيناريو | العقد | العمليات الناجحة | p50 | p95 | النتيجة التشغيلية |
|---|---:|---:|---:|---:|---|
| شبكة سليمة | 4 | 10/10 | 18.716661 ms | 20.156456 ms | صفر أخطاء وصفر تعارضات |
| عقدة Byzantine واحدة مع equivocation | 4 | 5/5 | 20.161349 ms | 20.328837 ms | اكتشاف التعارضات، صفر أخطاء تشغيلية |
| فقد رسائل 10% وتأخير 1 ms | 7 | 5/5 | 31.988882 ms | 34.579232 ms | retries وdrop handling، مع بقاء العمليات ناجحة |

في تجربة Byzantine ولّد المدقق المتعمد توقيعي `ACCEPT` و`ABANDON` لنفس capsule. سجلت العقد التعارضات، ولم يُغلق فرعان متعارضان. هذه النتيجة تثبت سلوك الرفض والكشف في هذا السيناريو المحدد، ولا تثبت مقاومة كل جداول Byzantine التكيفية الممكنة.

## crash/restart وWAL

في التجربة متعددة العمليات قُتلت العقدة `w1` أثناء طلب submit، وأُعيد تشغيلها على نفس ملف SQLite. عاد الطلب الذي انقطع بسبب `ConnectionResetError` إلى مسار recovery، ثم نجح إغلاق capsule المتأثرة، ونجحت العملية التالية أيضًا. بعد إعادة فتح ملف التخزين كانت سلامة SQLite صحيحة، واحتوى ملف العقدة المستعادة على 4 capsules و16 receipt و7 closure وseal_current واحدة؛ الزيادة في عدد closure ناتجة عن persistence وإعادة الإعلان أثناء recovery وليست forks مقبولة.

هذه التجربة تثبت **استعادة الحالة من WAL في التنفيذ المرجعي**. لا تزال هناك حاجة إلى اختبار power-loss حقيقي على بيئة تخزين فعلية، وفحص fsync عبر طبقات نظام الملفات، وسياسة backup/restore موثقة ومختبرة تحت امتلاء القرص.

## partition وعودة liveness

قُسمت شبكة من أربع عقد إلى مجموعتين `w0,w1` و`w2,w3`. فشل submit في القسم المنعزل مع `closure timeout` لأن وزن أي قسم أقل من عتبة الإغلاق. بعد إعادة الاتصالات إلى جميع الأقران، أُعيد إعلان capsule، نجح الإغلاق بزمن نهائي 11.0344 ms، وأثبتت جميع قواعد البيانات `integrity_check=true` مع closure واحدة لكل عقدة.

هذه هي الخاصية المطلوبة: **safety لا يتنازل عن نفسه أثناء partition، وliveness يتوقف عندما لا يتوفر quorum ثم يعود بعد healing**. التجربة محلية وليست شبكة WAN، ولذلك لا تكفي وحدها لادعاء تحمل كل ظروف الشبكات الجغرافية أو NAT أو ازدحام الإنتاج.

## model checking وخصائص البروتوكول

فحصت الأداة `benchmarks/model_check_mosaic.py` فضاءً محدودًا قابلًا لإعادة الإنتاج. في M1 جرى اختبار 84 تركيبًا من أحجام اللجان ووزن Byzantine المقبول، مع 36,703 زوجًا من quorums، ولم يظهر زوجان يفتقدان witness صادقًا في التقاطع. كما نجحت اختبارات M2 لمنع apply بلا closure صالح، وM3 لإصدار conflict evidence عند equivocation المحلي، وM4 لمنع abandon بعد closure، وM5 لفصل epoch، وM6 لذرية bundle عند حد visibility.

لا تزال M7 وM8 بحاجة إلى تمثيل رسمي مستقل في checker أو specification executable بدل الاكتفاء بعبارات السلامة الحالية. كذلك يجب تحويل البرهان المحدود إلى proof artifact رسمي قبل استخدامه في ورقة أو معيار.

## ما أصبح جاهزًا فعليًا

| المكوّن | حالة الإصدار |
|---|---|
| StateSeal وCapsule وWitnessReceipt وClosureProof | منفذ ومختبر |
| First-Claim Lock ومنع successor المزدوج | منفذ ومختبر |
| ConflictEvidence وAbandonProof وBundleClosure | منفذ ومختبر |
| leaderless receipt gossip | منفذ ومختبر على عمليات TCP مستقلة |
| SQLite WAL وcheckpoint وintegrity check | منفذ ومختبر مع reopen وrestart |
| Ed25519 وAES-GCM CapabilityVault وHKDF | منفذ ومختبر |
| ReplayGuard وTokenBucket | منفذ ومختبر |
| key isolation | مطبق؛ المفتاح الخاص المحلي لا يُحمل على العقد الأخرى |
| TLS/mTLS اختياري | منفذ في daemon وnetwork |
| weighted membership وepoch/committee interfaces | منفذ ومختبر |
| daemon CLI وconfig template | منفذ وقالب التشغيل موثق |

## ما يمنع إعلان الجاهزية العامة الكاملة

لا تزال نسخة MOSAIC الحالية شبكة validators ثابتة أو مصرحًا بها، وليست permissionless بالكامل. نموذج Sybil الاقتصادي المفتوح، ودفع/حجز stake، والخروج الآمن، والـslashing، واختيار لجنة عشوائيًا عبر VRF أو beacon لامركزي لم تُستكمل كمنظومة إنتاجية واحدة. كما لا توجد بعد آلة عقود ذكية عامة أو execution engine deterministic أو state-root authenticated storage كاملة.

كذلك لم تُنفذ بعد مقارنة binary موحدة مع HotStuff وNarwhal/Tusk وSui Lutris على نفس الأجهزة ونفس workload؛ الموجود حاليًا هو مقارنة مرجعية داخلية وقياسات MOSAIC مستقلة. لا يجوز تحويل p95 المحلي إلى ادعاء أنه أسرع من تلك الأنظمة قبل تشغيل baselines حقيقية قابلة للمقارنة.

وتبقى الحاجة قائمة إلى reliable delivery أو availability layer أقوى من retries المحدودة، حدود DoS مُثبتة، aggregate signatures، formal verification غير محدود، adaptive Byzantine schedules متعددة، power-loss testing، fuzzing طويل المدة بميزانية كبيرة، ومراجعة تشفيرية وشبكية مستقلة.

## طريقة التشغيل

القالب القابل للملء موجود في [`mosaic_node_config.example.json`](mosaic_node_config.example.json)، وشرح المفاتيح وWAL وmTLS في [`mosaic_production_config_ar.md`](mosaic_production_config_ar.md). بعد استبدال القيم السرية وتشغيل كل عقدة على ملفها الخاص:

```bash
cd /home/ubuntu/blockchain_alt
python3 -m mosaic.daemon --config /etc/mosaic/node-w0.json
```

يجب اعتبار القالب إعدادًا لشبكة داخلية أو validators موثوقين حتى تكتمل طبقة العضوية المفتوحة، والتشغيل عبر public internet، والتدقيق المستقل.

## الحكم النهائي

**MOSAIC الآن تنفيذ مرجعي موزع قوي وقابل للتشغيل، وليس مجرد فكرة أو نموذج لعبة.** اجتاز اختبارات السلامة الأساسية، crash/restart، partition، Byzantine equivocation، fuzzing، وقياس شبكة TCP مستقلة. لذلك يمكن الانتقال إلى pilot داخلي محدود بعقد مستقلة ومراقبة وسجلات ونسخ احتياطية.

لكن الحكم العلمي والمهني يظل: **جاهز لـpermissioned pilot، غير جاهز بعد كشبكة permissionless عامة أو كبديل مثبت تفوقه على جميع البلوكشينات التقليدية**. هذا هو الحد الذي تسمح به الأدلة الحالية دون مبالغة.

## المراجع والـartifacts

[1]: `mosaic_network_4_healthy_final.json` — نتيجة شبكة سليمة من أربع عقد.

[2]: `mosaic_network_4_byzantine_final.json` — نتيجة Byzantine equivocation بعد الإصلاح.

[3]: `mosaic_network_7_drop_final.json` — نتيجة فقد رسائل وتأخير على سبع عقد.

[4]: `mosaic_crash_restart.json` — نتيجة قتل عقدة وإعادة تشغيلها من WAL.

[5]: `mosaic_partition.json` — نتيجة partition ثم healing.

[6]: `mosaic_model_check.json` — تقرير bounded model checking.

[7]: `mosaic_node_config.example.json` — قالب إعداد daemon الإنتاجي.
