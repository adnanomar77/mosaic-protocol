# MOSAIC — تقرير التصميم والاختبار النهائي

## الملخص

MOSAIC هو اسم مؤقت لبروتوكول سجل موزع مبني من مبدأ مختلف عن البلوكشين التقليدي: لا يجعل الحقيقة ترتيبًا عالميًا للمعاملات، بل يجعلها **انتقالًا فريدًا لحالة خطية** يمكن إغلاقه بشهادة محلية. وحدة البروتوكول هي `Capsule` تستهلك `StateSeal` سابقًا وتنتج ختمًا لاحقًا. إذا ظهرت محاولتان مختلفتان من predecessor واحد، لا يختار النظام فرعًا فائزًا؛ بل ينشئ `ConflictEvidence` يمنع إغلاق الفرعين تحت فرضية النصاب.

هذه الفكرة ليست معلنة هنا على أنها اختراع 100% أو بديل إنتاجي مثبت. فحص السوابق وجد قربًا واضحًا من UTXO/eUTXO وFastPay وSui Lutris وReconfigurable Atomic Commit وThunderbolt، إضافة إلى براءات في conflict-aware ordering. المرشح الضيق للجدة هو **جبر الإغلاق الذي يثبت فرادة successor، ويحوّل التعارض إلى دليل إبطال، ويربط atomic bundle بقابلية الصرف بعد إغلاق جميع المجالات بدل rollback عالمي**. هذا المرشح يحتاج برهانًا أعمق ومقارنة رسمية قبل أي ادعاء ملكية فكرية.

## 1. ما الذي صُمّم؟

| العنصر | تعريف MOSAIC |
|---|---|
| الحقيقة | `StateSeal` للحالة الحالية، لا block height ولا ترتيب عالمي |
| العملية | `Capsule` موقعة تستهلك predecessor وتنتج successor |
| التحقق | تحقق محلي من التوقيع والقاعدة والـcapability والحقبة |
| الإغلاق | أكثر من ثلثي وزن الشهود يوقعون successor نفسه |
| التعارض | `ConflictEvidence` بدل ترتيب فرعين أو اختيار قائد للفوز |
| الاسترداد | `AbandonProof` يحرر محاولة عالقة قبل محاولة جديدة |
| الذرية | `BundleClosure` يجعل outputs غير قابلة للصرف حتى تكتمل closures المطلوبة |
| العضوية | لجنة موزونة بالـstake في النموذج المرجعي |
| النقل | TCP برسائل مؤطرة في تجربة الشبكة متعددة العمليات |

لا توجد سلسلة كتل في MOSAIC. يمكن الاحتفاظ بتاريخ الأختام لأغراض التدقيق والتقليم، لكن صحة الحالة لا تعتمد على إعادة تشغيل log عالمي مرتب. العملية المستقلة عن predecessor آخر لا تحتاج ترتيبًا بالنسبة إليه.

## 2. الآلية الأساسية

كل predecessor يملك capability منطقية أحادية الاستعمال. عندما يستقبل الشاهد كبسولة صحيحة، يصدر `WitnessReceipt(ACCEPT)` ويضع First-Claim Lock لذلك predecessor. لا يستطيع الشاهد الصادق إصدار receipt لقبسولة أخرى من predecessor نفسه. عند جمع وزن يتجاوز ثلثي اللجنة، ينشئ النظام `ClosureProof`.

إذا أصدر العميل كبسولتين مختلفتين من predecessor واحد، يمكن للمدقق حفظ التوقيعين كدليل تعارض. وجود الدليل لا يقرر أن إحدى المعاملتين فازت؛ بل يجعل الإغلاقين غير صالحين في هذا النموذج، وتحتاج الحالة إلى سياسة abandonment أو تحقيق مصدر capability. هذا يختلف عن نظام يفرض total ordering ثم يترك orderer يقرر أي transaction تُنفذ أولًا.

في المعاملة متعددة المجالات، لا تصبح المخرجات `spendable` عند إغلاق مجال واحد. تُحفظ كـ`PendingCapability` حتى تتوافر `ClosureProof` لكل predecessor مطلوب ويُنشأ `BundleClosure` واحد. بعدها تُطبّق successors معًا في مرحلة preflight ثم commit، بحيث لا يطبق النموذج جزءًا من bundle إذا كان جزء آخر ناقصًا.

## 3. نموذج الأمان

النموذج المستهدف يفترض لجنة موزونة مجموعها `N`، ووزن Byzantine أقل من `N/3`، وشبكة partially synchronous بعد GST. التوقيعات وhashes غير قابلة للكسر، والعضوية في v0.1 تأتي من snapshot مقبول مسبقًا. هذه ليست عضوية permissionless مكتملة؛ مقاومة Sybil الاقتصادية، randomness لاختيار اللجنة، وتغيير العضوية اللامركزي ما زالت أعمالًا مطلوبة.

### حجة عدم وجود إغلاقين

إذا وُجد `Closure(D1)` و`Closure(D2)` مختلفان من predecessor نفسه، فكل closure يملك وزنًا أكبر من `2N/3`، وبالتالي يتقاطع مجموع الموقعين في وزن أكبر من `N/3`. وبما أن Byzantine weight أقل من `N/3`، يوجد شاهد صادق في التقاطع. قاعدة First-Claim Lock تمنع الشاهد الصادق من توقيع successor مختلف من predecessor نفسه؛ وهذا تناقض. لذلك لا يتعايش الإغلاقان في النموذج.

هذه حجة safety مشروطة، وليست برهانًا آليًا كاملًا. لم تُكتب بعد صياغة TLA+/Ivy/Coq أو Lean، ولم تُحل كل حالات إعادة التهيئة والتخزين والاسترداد تحت crash.

## 4. فحص السوابق والجدة

فحصنا أعمالًا تمثل مسارات مختلفة حتى لا نخلط التصميم الجديد بإعادة تسمية تقنية موجودة.

| السابقة | ما وجدناه | أثرها على ادعاء MOSAIC |
|---|---|---|
| Cardano EUTXO | مدخلات تُستهلك مرة واحدة، تحقق محلي، وتوازٍ للمدخلات غير المتعارضة [1] | StateSeal وsingle-use capability ليسا جديدين منفردين |
| FastPay | Byzantine Consistent Broadcast ومدفوعات سريعة دون full atomic commit [2] | غياب الترتيب العالمي لكل payment معروف |
| Sui Lutris | consensusless path للمعاملات المؤهلة وترتيب للمتعارضة، مع objects وإعادة تهيئة [3] | fast path والـowned objects سابقة قريبة جدًا |
| Formalized Ledger Objects | تعريف رسمي للسجل وضمانات atomic/sequential/eventual consistency [4] | formal state object ليس جديدًا بذاته |
| Reconfigurable Atomic Commit | TCS وatomic commit عابر للشظايا مع براهين وإعادة تهيئة [5] | bundle closure يجب ألا يكون مجرد اسم جديد لـTCS/2PC |
| Thunderbolt | EOV/OE، DAG coordination، cross-shard execution، وإعادة تهيئة غير حاجزة [6] | التوازي والذرية الحديثة لهما سوابق متقدمة |
| US12141125B2 | read-set/write-set وordering service لتقليل تعارضات commit [7] | conflict-aware ordering موجود حتى في براءة فعالة |

النتيجة العلمية المنضبطة هي أن MOSAIC **ليس مثبت الجدة المطلقة**. ما يمكن الدفاع عنه مؤقتًا هو فرضية آلية ضيقة: فرادة successor محليًا، evidence يمنع الإغلاقين، وbundle visibility مؤجلة بدل rollback. يجب أن تثبت المواصفة أن هذا التركيب يحقق invariant أو حد أداء لا تحققه السوابق القريبة.

## 5. ما بُني فعليًا

النموذج المرجعي موجود في مجلد `mosaic/` ويضم StateSeal وCapsule وWitnessReceipt وClosureProof وConflictEvidence وAbandonProof وBundleClosure. كما يضم بروتوكولًا يطبق First-Claim Locks، وweighted threshold، وتحققًا مستقلًا من الشهادات، وapply ذريًا للحزم.

أُضيف نقل TCP مستقل العملية. لكن يجب توضيح قيد مهم: تجربة النقل تستخدم `w0` كجامع receipts لتبسيط النموذج، لذلك فهي **شبكة موزعة حقيقية لكنها ليست تنفيذًا leaderless كاملًا**. في التصميم النظري لا يلزم قائد دائم، أما إزالة جامع receipts من المسار التنفيذي فتحتاج gossip أو threshold aggregation أو collector rotation إضافية.

## 6. نتائج الاختبارات

نجحت **25 اختبارات pytest**، إضافة إلى `compileall`، وتشمل الاختبارات المحلية:

| الفئة | التحقق |
|---|---|
| فرادة successor | منع قبول فرعين من predecessor واحد |
| الشهادات | رفض التوقيع المعدل وproof غير المسجل |
| النصاب | استخدام الوزن لا عدد المفاتيح |
| abandon | تحرير محاولة عالقة ثم قبول attempt جديدة |
| bundle | رفض التطبيق الجزئي وتطبيق جميع successors معًا |
| الشبكة | انتقال الرسائل والتوقيعات بين عمليات مستقلة |

### نتائج شبكة TCP

كل حالة استخدمت خمس عمليات. القياسات localhost، وليست WAN.

| العقد | الحالة | النجاح | p50 ms | p95 ms | الملاحظة |
|---:|---|---:|---:|---:|---|
| 4 | سليم | 5/5 | 5.1894 | 5.4177 | 0 أخطاء |
| 7 | سليم | 5/5 | 8.4121 | 10.8179 | 0 أخطاء |
| 4 | delay 1ms + drop 10% | 5/5 | 10.3768 | 10.8479 | retries نجحت |
| 7 | delay 1ms + drop 10% | 5/5 | 13.8462 | 14.6602 | retries نجحت |
| 4 | Byzantine واحد | 5/5 | 5.5886 | 5.9917 | كشف 5 تعارضات |
| 7 | Byzantine واحد | 5/5 | 8.1282 | 8.2001 | كشف 5 تعارضات |

العقدة Byzantine أرسلت `ACCEPT` ثم `ABANDON` موقّعين للكبسولة نفسها. لم يُحتسب `ABANDON` في quorum، وسجل القائد التعارض حتى عندما وصل بعد تكوين closure. هذا يثبت كشف نمط واحد من equivocation، لا كل الهجمات الممكنة.

### benchmark النموذج المرجعي

القياس التالي يستخدم Ed25519 وreceipts حقيقية داخل عملية Python واحدة، ولا يشمل network latency أو scheduling بين أجهزة.

| الحمل | Ops/s | p50 ms | p95 ms | bytes/op |
|---|---:|---:|---:|---:|
| كبسولات مستقلة | 319.2297 | 3.0861 | 3.2341 | 1,649.8 |
| مورد واحد متسلسل | 336.8428 | 2.9185 | 3.0323 | 1,658.8 |
| حزمة موردين | 140.0776 | 7.0384 | 7.2071 | 3,321.2 |

توضح الأرقام أن كلفة bundle تقارب ضعف كلفة العملية المحلية، وهو أمر متوقع من إضافة closure ثانية وحاجز ذرية. لذلك لم يثبت MOSAIC تفوقًا عامًا؛ بل كشف بوضوح مكان التحسين الحقيقي المطلوب.

## 7. ما الذي أصبح حقيقيًا؟

أصبح لدينا **بروتوكول مرجعي قابل للتشغيل** وليس مجرد فكرة أو مخطط. يمكن إنشاء كبسولة موقعة، نقلها عبر TCP إلى عقد مستقلة، جمع receipts، إصدار closure، تطبيق successor، اختبار تعارض، واسترداد محاولة abandoned. هذه درجة حقيقية من الاكتمال التجريبي.

لكن النظام ليس production-complete. لا توجد بعد smart-contract VM، ولا committee randomness لا مركزية، ولا threshold BLS، ولا تخزين authenticated دائم، ولا formal machine-checked proof، ولا اختبار WAN أو crash/recovery شامل، ولا مقارنة binaries رسمية متطابقة مع HotStuff/Narwhal/Tusk/Sui. لذلك لا يجوز تسميته «أفضل من كل شيء» أو «ثورة مثبتة».

## 8. الحكم النهائي

**الحكم:** MOSAIC فرضية بروتوكولية جادة مع نموذج مرجعي موزع ونتائج اختبار أولية ناجحة، لكنه ليس ابتكارًا مثبت الجدة المطلقة ولا نظامًا إنتاجيًا كاملًا بعد.

الجزء الذي يستحق مواصلة البحث ليس اسم MOSAIC ولا استخدام hash أو signatures أو quorum. الجزء القابل للدفاع هو محاولة جعل **الإغلاق شهادة فرادة انتقال، والتعارض evidence يمنع الإغلاقين، والذرية خاصية قابلية صرف مؤجلة**. إذا أثبتت الصياغة الرسمية أن هذا يزيل تنسيقًا لا تستطيع السوابق القريبة إزالته، فقد يصبح أساس ورقة علمية أو براءة. وإذا اتضح أنه مكافئ لـUTXO أو FastPay أو Sui أو TCS، فسيكون مساهمة هندسية مفيدة لكن ليس اختراعًا جذريًا.

## 9. الخطوات اللازمة قبل الإصدار العام

| الأولوية | العمل المطلوب |
|---:|---|
| 1 | بناء نموذج رسمي machine-checked لـM1–M8 مع حالات Byzantine وabandon وepoch transition |
| 2 | استبدال جامع `w0` ببروتوكول aggregation موزع أو rotating collectors |
| 3 | إضافة committee randomness وmembership transition وSybil economics |
| 4 | تنفيذ crash/restart وpartition وmessage reordering وadaptive Byzantine schedules |
| 5 | تشغيل baselines الرسمية في حاويات reproducible وبنفس workload |
| 6 | فحص براءات احترافي لمطالبات claims قبل أي تسجيل ملكية فكرية |

## 10. أوامر إعادة الإنتاج

```bash
cd /home/ubuntu/blockchain_alt
python3 -m pytest
python3 -m compileall -q mosaic benchmarks tests
python3 -m benchmarks.mosaic_benchmark
python3 -m benchmarks.run_mosaic_network --nodes 4 --operations 10 --base-port 19800
python3 -m benchmarks.run_mosaic_network --nodes 4 --operations 5 --base-port 19520 --byzantine-id w1
python3 -m benchmarks.run_mosaic_network --nodes 7 --operations 5 --base-port 19700 --delay-ms 1 --drop-rate 0.10
```

## المراجع

[1] [Cardano, Extended UTXO model](https://docs.cardano.org/about-cardano/learn/eutxo-explainer)

[2] [Baudet, Danezis, Sonnino, FastPay: High-Performance Byzantine Fault Tolerant Settlement](https://arxiv.org/abs/2003.11506)

[3] [Blackshear et al., Sui Lutris: A Blockchain Combining Broadcast and Consensus](https://arxiv.org/abs/2310.18042)

[4] [Fernández Anta et al., Formalizing and Implementing Distributed Ledger Objects](https://arxiv.org/abs/1802.07817)

[5] [Bravo and Gotsman, Reconfigurable Atomic Transaction Commit](https://arxiv.org/abs/1906.01365)

[6] [Chen et al., Thunderbolt: Concurrent Smart Contract Execution with Non-blocking Reconfiguration for Sharded DAGs](https://arxiv.org/abs/2407.09409)

[7] [IBM, US12141125B2 — Transaction reordering in blockchain](https://patents.google.com/patent/US12141125B2/en)
