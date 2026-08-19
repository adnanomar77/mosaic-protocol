# MOSAIC Production Definition v1

## الهدف الفعلي

الإصدار المطلوب ليس «فكرة محسنة» ولا benchmark داخل عملية واحدة. الهدف هو شبكة MOSAIC قابلة للتشغيل كخدمة موزعة من عدة عقد مستقلة، تستطيع إعادة التشغيل بعد الانقطاع، تخزين الحالة دائمًا، التحقق من العضوية والحقب، إصدار closures دون جامع مركزي دائم، كشف equivocation، ورفض replay والرسائل المشوهة.

الإصدار الأول سيكون **شبكة حالات وكائنات عامة موقعة** مع smart-contract rules محدودة deterministic، وليس VM عامة تورنغية. هذا التقييد مقصود حتى لا ندعي اكتمالًا زائفًا في بيئة عقود لم تُدقّق.

## تعريف «كامل» في هذا المشروع

| المجال | معيار القبول |
|---|---|
| الاستقلال | لا يعتمد المسار الحرج على `w0` أو جامع مركزي دائم |
| العضوية | genesis membership root، stake، epochs، admission/exit، ومنع إعادة استخدام الودائع |
| اختيار اللجنة | seed قابل للتحقق، اختيار موزون، proof of selection، وعزل الحقبة |
| السلامة | منع إغلاقين، منع apply بلا closure، منع replay، ومنع شهادة من لجنة قديمة |
| الحيوية | retries، timeouts قابلة للتحقق، recovery، وقيود واضحة تحت partition |
| التخزين | WAL/SQLite أو Badger مكافئ، fsync policy، checkpoint، واستعادة بعد crash |
| النقل | framing، authentication، limits، backpressure، rate limits، وTLS أو channel authenticated |
| التشغيل | config، CLI، health/readiness، metrics، structured logs، graceful shutdown |
| التدقيق | اختبارات خصوم، property tests، fuzzing للرسائل، وتقرير قابل لإعادة الإنتاج |
| الخصوصية | على الأقل عدم تسريب capability secret، مع تصميم قابل لإضافة commitments لاحقًا |
| التوثيق | protocol spec، threat model، migration/upgrade rules، وrunbook |

## الفجوات الحالية

| الفجوة | الوضع السابق | الإصلاح المطلوب |
|---|---|---|
| جامع receipts | `w0` في runner | peer-to-peer receipt gossip مع rotating aggregation أو threshold combine |
| committee selection | members ثابتون | Epoch seed + weighted deterministic selection + proof |
| العضوية | snapshot مبسط | admission/exit certificates وstake lock وslashing evidence |
| التخزين | ذاكرة العملية | WAL durable state + recovery journal + checkpoints |
| replay | جزئي | anti-replay cache، nonce/attempt، epoch domain separation، limits |
| الشبكة | TCP demo | authenticated channels، framing limits، backpressure، reconnection |
| التهديد | Byzantine محدود | scheduler خصومي، partitions، crash/restart، adaptive messages |
| الخصوصية | capability hash | secret handling وcommitment abstraction |
| التحقق الرسمي | حجج نصية | model checking لـM1–M8 ثم proof artifacts |
| التشغيل | runner | daemon/CLI/config/metrics/logging/health |

## سياسة الصدق

لن يسمى الإصدار «mainnet ready» لمجرد أن pytest ينجح. سيحمل كل ضمان نطاقه: safety تحت وزن Byzantine أقل من الثلث، liveness تحت partial synchrony وبعد GST، storage durability وفق fsync mode المحدد، وprivacy فقط بالقدر الذي يثبته التصميم.

إذا بقيت عضوية الشبكة قائمة على genesis/validator set مع stake، فسيعلن الإصدار **production-ready for federated or curated validator networks**، وليس permissionless public L1. الانتقال إلى permissionless يتطلب اقتصادًا كاملًا، توزيعًا لا مركزيًا للهوية والـstake، randomness مقاومًا للتلاعب، وآلية bootstrapping لا تفترض الثقة في مشغل واحد.

## معايير الخروج

لا نخرج بإصدار تشغيلي إلا إذا: نجح recovery بعد قتل كل عقدة في نقاط WAL محددة؛ لم ينتج model checker حالة safety مخالفة ضمن حدود البحث؛ نجحت fuzzing الرسائل دون crash أو apply غير صحيح؛ عملت شبكة من 4 و7 عقد دون جامع دائم؛ نجحت تجارب drop/reorder/partition المحدودة؛ وكانت كل النتائج والـhashes محفوظة في التقرير النهائي.
