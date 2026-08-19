# MOSAIC Permissionless Acceptance Matrix

## الغرض

يحدد هذا المستند الحد الفاصل بين **نواة MOSAIC الحالية** وبين شبكة permissionless عامة يمكن تشغيلها دون قائمة validators موثوقة مسبقًا. لا يُسمح بإعلان الجاهزية العامة إلا بعد اجتياز جميع البوابات الحرجة، وليس بعد نجاح اختبارات الإغلاق المحلي وحدها.

> الجاهزية العامة ليست خاصية واحدة. هي حاصل اجتماع السلامة، العضوية المفتوحة، اقتصاد Sybil، اختيار اللجان، توفر البيانات، التنفيذ، التخزين، التشغيل، المراجعة، والقياس المقارن.

## خط الأساس المثبت حاليًا

النسخة الحالية تحقق شبكة validators ثابتة بوزن stake مهيأ مسبقًا، receipt gossip بلا جامع مركزي، First-Claim Lock، ClosureProof، ConflictEvidence، AbandonProof، BundleClosure، SQLite WAL، استعادة restart، عزل مفاتيح، ReplayGuard، TokenBucket، TLS اختياري، وdaemon TCP مستقل. نتائج الإصدار موجودة في ملفات `docs/mosaic_*.json` وفي التقرير `MOSAIC_production_release_ar.md`.

هذه القدرات تُصنف **P0-Permissioned Pilot**. لا تعني وحدها أن أي طرف مجهول يستطيع الانضمام أو أن اللجنة المستقبلية غير قابلة للتلاعب.

## واجهة الشبكة العامة المستهدفة

تحتاج الشبكة العامة إلى كائنات موقعة ومحددة الإصدار، مع domain separation وcanonical encoding، وفق الواجهات الآتية:

| الكائن | الوظيفة المطلوبة | الحقول الحرجة |
|---|---|---|
| `ValidatorIdentity` | ربط هوية المدقق بمفتاحه ومعلومات تشغيله | `validator_id`, `public_key`, `network_endpoints`, `protocol_version`, `metadata_hash` |
| `StakeBond` | إثبات قفل stake اقتصاديًا | `bond_id`, `owner`, `amount`, `asset`, `activation_epoch`, `unlock_epoch`, `signature` |
| `AdmissionRequest` | طلب انضمام permissionless | `identity`, `bond`, `capabilities`, `nonce`, `signature` |
| `MembershipSnapshot` | الحالة canonical للعضوية والوزن | `epoch`, `validators`, `total_weight`, `snapshot_root`, `transition_proof` |
| `RandomnessBeacon` | مصدر عشوائية غير قابل للتحكم من طرف واحد | `epoch`, `round`, `commitment_root`, `reveal_root`, `beacon_value`, `proof` |
| `CommitteeSelectionProof` | إثبات أن اللجنة اختيرت من snapshot وبذرة صحيحة | `epoch`, `beacon_digest`, `committee_ids`, `weights`, `proof` |
| `SlashEvidence` | إثبات equivocation أو مخالفة قابلة للعقوبة | `offender`, `conflicting_objects`, `witness_signatures`, `evidence_digest` |
| `WithdrawalReceipt` | خروج آمن بعد فترة انتظار | `validator_id`, `amount`, `unlock_epoch`, `snapshot_digest`, `proof` |
| `AvailabilityCertificate` | إثبات نشر capsule/receipts أو قدرة استرجاعها | `object_id`, `shard_commitments`, `responders`, `weight`, `proof` |
| `ExecutionReceipt` | نتيجة تنفيذ deterministic قابلة لإعادة التحقق | `capsule_id`, `pre_state_root`, `post_state_root`, `gas_used`, `event_root`, `proof` |

كل كائن جديد يجب أن يحدد الإصدار، epoch، nonce، digest، قواعد التحقق، وحدود الحجم. لا يُقبل إدخال كائن إلى consensus قبل وجود اختبار رفض للتلاعب وإعادة الإرسال وcross-epoch replay.

## بوابات القبول

| البوابة | معيار النجاح الإلزامي | الحالة الحالية |
|---|---|---|
| G0 — Regression | جميع اختبارات MOSAIC الحالية ناجحة، مع إعادة إنتاج نتائج WAL وByzantine وpartition | منجز |
| G1 — Permissionless admission | يستطيع validator جديد إنشاء identity وstake bond والانضمام دون تعديل يدوي لملفات العقد، مع تفعيل مؤجل وproof قابل للتحقق | غير منجز |
| G2 — Sybil economics | تكلفة الهوية مرتبطة stake حقيقي، مع حد أدنى، activation delay، exit delay، ومخاطر/عقوبات تجعل إنشاء هويات كثيرة غير مجاني | غير منجز |
| G3 — Slashing | evidence تعارض قابل لإعادة التحقق يؤدي إلى عقوبة deterministic ولا يمكن للمخالف الإفلات بتغيير المفتاح أو epoch | غير منجز |
| G4 — Random committee | اختيار لجان موزون بــVRF أو beacon لا مركزي، مع إثبات قابل للتحقق، وتوزيع يقيس خطر احتكار اللجنة | غير منجز |
| G5 — Epoch transition | انتقال عضوية atomically مع حماية replay، وعدم قبول لجنة قديمة في epoch جديد | جزئي |
| G6 — Public network | عقد WAN مستقلة تعمل خلف شبكات مختلفة، مع discovery، connection limits، backpressure، retries موثوقة، وavailability | جزئي |
| G7 — DoS bounds | حد أعلى مثبت للذاكرة، الاتصالات، حجم الرسائل، العمل التشفيري، ومعدل الطلب لكل هوية وpeer | جزئي |
| G8 — General execution | deterministic execution engine، state roots، gas/resource accounting، وcomposability أو تحديد رسمي لنطاق عدم وجود total order | غير منجز |
| G9 — Durable operation | snapshots، restore، migration، pruning، key rotation، power-loss، امتلاء القرص، وupgrade rollback | جزئي |
| G10 — Formal safety | model checking أوسع لـM1-M8 وبرهان مستقل لعدم وجود إغلاقين تحت نموذج الوزن والـByzantine | جزئي |
| G11 — Public testnet | testnet لمدة طويلة بعقد مستقلة ومراقبة، fault injection، churn، adaptive Byzantine، وقياس availability | غير منجز |
| G12 — Fair comparison | binary benchmarks ضد baselines محددة بنفس workload والعتاد والدلالة، مع نشر raw data وscripts | غير منجز |
| G13 — Independent review | مراجعة تشفير وشبكة واقتصاد وتنفيذ من طرف مستقل، مع إغلاق findings الحرجة | غير منجز |
| G14 — Release gate | لا توجد فجوة P0، وكل P1 لها owner وموعد وخطة rollback، وتصدر مواصفة wire versioned ونهائية | غير منجز |

## تصنيف المخاطر

الفجوات G1 إلى G5 هي مخاطر **سلامة عضوية واقتصاد**؛ والفجوات G6 إلى G9 مخاطر **تشغيل وavailability**؛ والفجوات G10 إلى G13 مخاطر **إثبات ومصداقية وقياس**. لا يجوز تعويض فشل بوابة من فئة السلامة بقياس latency أفضل.

## معايير عدم الادعاء

حتى بعد اجتياز G0 إلى G10 لا يُقال إن MOSAIC «أفضل من جميع البلوكشينات». يُسمح فقط بادعاء محدود من نوع: «يتفوق في workload محدد وتحت إعداد محدد وفق مقاييس محددة». يلزم تشغيل baselines binary مستقلة قبل أي ادعاء أداء عام، كما يلزم تدقيق مستقل قبل أي ادعاء أمان إنتاجي.

## خطة التنفيذ المرتبطة

يبدأ التنفيذ من G1 وG2 ببناء lifecycle كامل للـstake والعضوية، ثم G4 لاختيار اللجنة، وبعدها G6 وG7 للشبكة العامة، ثم G8 للتنفيذ العام، وG9 وG10 للتشغيل والإثبات، وأخيرًا G11 إلى G14 قبل إصدار public testnet أو mainnet. كل مرحلة تضيف اختبارات قبول وتترك artifact قابلًا لإعادة الإنتاج.
