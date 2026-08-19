# MOSAIC — تقرير التقدم نحو permissionless العامة

## الحكم المختصر

نُفذت بالفعل طبقات جديدة كانت تمنع MOSAIC من تجاوز permissioned pilot: دورة stake قابلة للتحقق، withdrawal delay، slashing evidence، randomness commit-reveal، اختيار لجان مرتبط بـbeacon، حدود شبكة عامة، availability certificates، deterministic execution kernel، execution binding، تخزين schema-versioned مع snapshots وmigration وpruning، مواصفة TLA+ أولية، واختبارات Byzantine متعددة العقد.

النتيجة الحالية هي **شبكة مرجعية متقدمة قابلة للتشغيل والاختبار، ومرشحة لـpublic testnet محدودة**. لكنها ليست بعد mainnet permissionless مكتملة؛ لأن بعض الطبقات المنفذة ما زالت reference protocol وليست اقتصادًا أو شبكة WAN عامة كاملة، ولأن المقارنة binary الرسمية والتدقيق المستقل لم يكتملَا.

## بوابة الإصدار الحالية

| المؤشر | النتيجة |
|---|---:|
| اختبارات pytest | 62/62 ناجحة |
| bounded model checking | M1–M8 ناجحة |
| quorum pairs في M1 | 36,703 زوجًا ضمن 84 حالة |
| adaptive Byzantine testnet | 7 عقد، عقدتان Byzantine، 20/20 عملية ناجحة |
| long testnet | 7 عقد، 30/30 عملية ناجحة، 5% drop، 2 ms delay |
| healthy 10-node network | 20/20 عملية ناجحة، p50 61.758052 ms، p95 72.236053 ms |
| crash/restart وpartition | ناجحان في اختبارات متعددة العمليات السابقة |
| TLC | غير مثبت؛ TLA+ موجودة كمواصفة أولية فقط |

## الطبقات التي أُضيفت

### العضوية المفتوحة واقتصاد Sybil

أصبحت وحدة العضوية تحتوي على `StakeBond` موقّع يربط bond بالمالك والمبلغ والأصل وفترة التفعيل والانتهاء. تتحقق `MembershipManager` من تطابق bond مع طلب admission، تمنع إعادة استخدام deposit، تطبق withdrawal delay، وتنتج `WithdrawalReceipt` بعد انتهاء فترة الانتظار.

أضيف `SlashEvidence` بمعرّف deterministic ومنع replay. عند ثبوت evidence متعارض ينخفض stake، وعند الوصول إلى الصفر يُعاقب المدقق ويخرج من snapshot واللجنة. هذا يحسن مقاومة Sybil، لكنه لا يمثل بعد ledger اقتصاديًا عامًا يحوي custody وrewards وfee market وsettlement لأصل مالي فعلي.

### العشوائية واختيار اللجان

أضيف مسار commit-reveal: يلتزم المدقق بـhash سر، ثم يكشف السر، ولا يُنشأ `RandomnessBeacon` إلا عند تحقق توقيعات صحيحة وبلوغ وزن reveals عتبة quorum. ترتبط `CommitteeSelectionProof` بقيمة beacon وبـproof_id، ويُرفض beacon من epoch قديم.

هذه طبقة صحيحة وقابلة للاختبار، لكنها تحتاج في الشبكة العامة إلى حوافز ضد عدم الكشف، fallback لا يتيح التحكم لطرف واحد، incentive-compatible beacon، وتكامل كامل مع epoch transition وstake settlement.

### الشبكة العامة وAvailability

أضيفت حدود `frame_timeout` و`connect_timeout`، حد اتصالات لكل peer، token bucket مستقل، حد pending capsules، وexponential retry backoff. كما أضيفت `AvailabilityAttestation` و`AvailabilityCertificate` ذات توقيعات Ed25519 ووزن quorum.

هذا يثبت قابلية رفض الرسائل البطيئة أو المفرطة والشهادات غير الكافية، لكنه ليس بعد erasure-coded data availability layer مع sampling وrepair ومقاومة data withholding على WAN.

### التنفيذ العام

أضيف deterministic execution kernel محدود بالعمليات `SET` و`DELETE` و`ADD_INT`. يحتوي على توقيع caller، nonce، gas limit، state root، event root، state diff digest، وatomic batch execution. أضيف `ExecutionBinding` لربط receipt بمعرّف capsule وpredecessor محددين.

هذه ليست VM عقود ذكية Turing-complete، ولم تُعلن كذلك. الخطوة التالية هي ربط receipt فعليًا بمسار closure وstate storage وإضافة resource accounting وcomposability متعددة الموارد قبل اختيار لغة عقود عامة.

### التخزين والتعافي

أصبح `DurableStore` schema-versioned مع migration additive، snapshots، pruning آمن للأحداث، WAL و`synchronous=FULL`، checkpoint، و`integrity_check`. ويرتبط كل closure الآن بـsnapshot للحالة الحالية.

نجح crash/restart المحلي متعدد العمليات وpartition ثم healing. ما زال power-loss الحقيقي، امتلاء القرص، restore من backup بعيد، migration rollback، وkey rotation التشغيلية بحاجة إلى اختبار مستقل طويل.

## نتائج testnet

في testnet طويلة من 7 عقد، 30 عملية، تأخير 2 ms، فقد رسائل 5%، وByzantine واحد، نجحت كل العمليات الثلاثون، وكان p50 نحو 36.749191 ms وp95 نحو 49.126423 ms، مع صفر أخطاء تشغيلية. وفي اختبار adaptive من 7 عقد، عقدتان Byzantine، 20 عملية، وتأخير 2 ms وفقد 3%، نجحت العمليات العشرون، وكان p50 نحو 42.456362 ms وp95 نحو 52.029440 ms، مع تسجيل التعارضات المتوقعة دون انهيار.

هذه النتائج **محلية ومتعددة العمليات** وليست شبكة WAN عامة. لذلك تثبت تحمل schedule محدد، ولا تثبت مقاومة كل جداول Byzantine التكيفية أو كل بيئات الإنترنت.

## المقارنة

أُعيد تشغيل controlled comparison الداخلي، لكن صفوف HotStuff-style وNarwhal/Tusk-style وSui Lutris-style فيه abstractions تنفيذية وليست binaries الرسمية. لذلك لم تُستخدم لإعلان تفوق MOSAIC.

المصادر الرسمية تفصل بوضوح بين benchmark setups المختلفة: مستودع libhotstuff يصف prototype implementation وتوجد فيه ملاحظات تشغيلية منفصلة، ومشروع Narwhal/Tusk يضم Rust implementation وbenchmark harness، بينما توثيق Sui يصف نتائج Mysticeti في controlled testing لا production metrics، وورقة Sui Lutris تعرض نتائجها ضمن إعدادها الخاص.[1] [2] [3] [4]

المقارنة العلمية النهائية تتطلب نفس العتاد، نفس عدد العقد، نفس حجم المعاملة، نفس تعريف finality، نفس شبكة WAN أو emulator، ونفس execution semantics، مع تشغيل binaries فعلية وraw data منشورة.

## ما يمنع إعلان mainnet permissionless الآن

الموانع الأساسية المتبقية ليست في وجود closure محلي أو WAL، بل في تحويل الطبقات المرجعية إلى بنية عامة كاملة:

| المانع | المطلوب قبل mainnet |
|---|---|
| اقتصاد permissionless | custody أو ledger stake فعلي، rewards، fees، slashing settlement، exit وrejoin policy |
| randomness العام | beacon incentive-compatible، non-reveal fallback، committee rotation proof، وعدم قابلية التأثير الاقتصادي |
| availability | erasure coding، sampling، repair، retention، وقياس data withholding |
| execution | VM أو لغة عقود deterministic، gas واقعي، cross-resource composability، وstate-root persistence |
| الشبكة | WAN testnet، discovery، NAT، churn، long-run monitoring، DoS bounds وbackpressure موزون |
| الإثبات | TLC/Apalache أو TLA+/Ivy/Coq/Lean checker مستقل، مع formal model يطابق الـwire objects |
| المقارنة | HotStuff/Narwhal/Sui binaries أو harnesses رسمية تحت workload موحد |
| المراجعة | تدقيق مستقل للتشفير والشبكة والاقتصاد والتنفيذ، وإغلاق findings الحرجة |

## الحكم النهائي

**نعم، يمكن تنفيذ الطريق إلى شبكة عامة، وقد بدأ تنفيذه فعليًا في المستودع.** MOSAIC لم يعد مجرد فكرة بحثية أو نموذجًا بسيطًا؛ أصبح reference network متقدمة واجتاز 62 اختبارًا، منها testnet متعددة العمليات وWAL وByzantine وavailability وexecution وmodel checking.

لكن التصنيف المهني الحالي هو:

> **MOSAIC Advanced Permissioned Reference Network / Pre-Public-Testnet — وليس Permissionless Mainnet بعد.**

السبب هو أن الجاهزية العامة تتطلب إغلاق الفجوات الاقتصادية والتشغيلية والإثباتية والمقارنة، لا مجرد إضافة classes أو رفع عدد الاختبارات. بعد تشغيل testnet WAN طويلة، وإكمال stake settlement وrandomness incentives وavailability وVM والتدقيق والمقارنة binary، يمكن رفع التصنيف تدريجيًا إلى public testnet ثم production mainnet.

## المراجع

[1]: https://github.com/hot-stuff/libhotstuff — مستودع libhotstuff الرسمي ووصف prototype implementation.

[2]: https://github.com/MystenLabs/narwhal — مستودع Narwhal/Tusk الرسمي وbenchmark harness.

[3]: https://docs.sui.io/develop/sui-architecture/consensus — توثيق Sui consensus وMysticeti والتمييز بين controlled results وproduction metrics.

[4]: https://arxiv.org/abs/2310.18042 — ورقة Sui Lutris ونتائجها ضمن إعدادها التجريبي.
