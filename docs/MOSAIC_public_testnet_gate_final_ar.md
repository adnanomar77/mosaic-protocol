# MOSAIC — تقرير بوابة Public Testnet وProduction Mainnet

**الإصدار:** بوابة التقييم المحدّثة بعد long-run v5.  
**النطاق:** permissionless economics، randomness، availability، deterministic execution، churn/restart، security، binary baselines، وخطة الانتقال إلى WAN.  
**الحكم الحالي:** **Advanced Permissioned Reference Network / Pre-Public-Testnet**. لم تُعلن الشبكة public testnet بعد، ولا تُعد production mainnet.

## 1. خلاصة تنفيذية

أصبح MOSAIC نظامًا موزعًا قابلًا للتشغيل التجريبي، لا مجرد مجموعة classes معزولة. تشمل الطبقة الحالية StateSeal وCapsule وWitnessReceipt وClosureProof وConflictEvidence وAbandonProof وBundleClosure، وشبكة TCP leaderless مع WAL SQLite وEd25519 وTLS/mTLS اختياري وعزل للمفاتيح، إضافة إلى settlement اقتصادي، commit-reveal beacon مع fallback، Reed-Solomon availability، تنفيذ deterministic مربوطًا بالإغلاق وجذور الحالة، onboarding، وسجل أحداث JSONL متسلسل بالهاش.

أُصلحت في هذه المرحلة مشكلة restart التي كانت تسجل `CapsuleInvalid: unknown predecessor seal` كخطأ تشغيلي عندما تصل capsule قبل اكتمال restore. أصبح مسار submit يصنف هذه الحالة كـprotocol rejection قابلة لإعادة المحاولة، وأصبح مسار closure يعاملها كرفض بروتوكولي. كما أصبح harness يوجه أول الطلبات بعد kill إلى validator سليم بينما تستعيد العقدة WAL، بدل تضخيم p95 بسبب إعادة المحاولة على عقدة في طور الإقلاع.

## 2. نتائج التحقق الحالية

| الفحص | النتيجة الحالية | الدلالة والحدود |
|---|---:|---|
| Python test suite | **87/87 ناجحة** | تغطية regression للمكونات المثبتة؛ ليست بديلًا عن تدقيق مستقل |
| Bounded model checker | **M1–M8 ناجحة** | invariants محدودة ضمن النموذج؛ ليست formal proof غير محدودة |
| Static AST security audit | **0 critical و0 medium** | فحص ساكن للنطاق المفحوص؛ لا يثبت غياب كل ثغرة تنفيذية |
| Wire/base64 fuzz | **4,000 حالة، 0 unexpected exception** | parser-level harness؛ لا يثبت سلامة كل state machine |
| Onboarding rehearsal | gate passed | 4 daemons في local multi-process emulation |
| Beacon rehearsal | مكتملة | commit/reveal/finalize عبر TCP مع settlement |
| Availability rehearsal | مكتملة | 5 providers، shard distribution، sampling، repair، WAL restart |
| Long-run v5 | **120/120 ناجحة، liveness=1.0** | 7 عقد محلية، Byzantine×2، kill/restart وDoS جزئي |
| Long-run safety signal | **errors=0** | conflicts الخاصة بـByzantine بقيت evidence/protocol conflicts |
| Long-run latency | **p50=37.520503 ms؛ p95=231.326768 ms** | localhost TCP؛ لا تمثل Internet WAN |
| Long-run cost | **179,015.28 bytes/success تقريبًا** | قياس harness محدد وليس benchmark عامًا لكل workload |
| DoS partial frames | **24 اتصالًا أُغلق** | تحقق تشغيلي من timeout/frame handling |
| Event log | **8 أحداث؛ verified=true** | hash-chained JSONL؛ digest خارجي عام ما زال مطلوبًا |
| HotStuff baseline | demo رسمي شُغّل | نحو 10,710 decisions في نحو 10 ثوانٍ؛ semantics وworkload مختلفان |
| Narwhal/Tusk baseline | لم يكتمل build | تعذر إنتاج رقم صالح للمقارنة في البيئة الحالية |

المصدر الأساسي للأرقام هو `testnet/artifacts/mosaic_testnet_long_final.json`، وسجل التشغيل هو `testnet/events/testnet-0-v5.jsonl`. تقرير long-run التفصيلي موجود في `docs/mosaic_testnet_long_ar.md`.

## 3. ما تم إنجازه في طبقات permissionless

أصبح `SettlementLedger` يحفظ bond وunbond وslash وrewards وfees مع persist/restore من WAL، وأصبح `MembershipManager` يربط العضوية والوزن الاقتصادي بالأدلة والتسوية بدل الاعتماد على جدول أوزان في الذاكرة فقط. توجد أيضًا دورة beacon commit/reveal/finalize مع fallback عند فشل reveal quorum، وتسوية incentives للعقد التي تكشف أو لا تكشف.

تعمل طبقة availability على Reed-Solomon في GF(256)، وتوزع k+m shards وتنفذ sampling وrepair مع WAL. ويرتبط التنفيذ deterministic بـCapsule وClosureProof وstate roots، مع عمليات SET وDELETE وADD_INT وgas وnonce وpersist/restore. هذه بنية permissionless أولية قابلة للاختبار، لكنها ليست بعد اقتصاد شبكة عامة مثبتًا ضد الأسواق أو الاحتكار أو collusion.

## 4. بوابة التصنيف

| التصنيف | الحالة الحالية | قرار الانتقال |
|---|---|---|
| Permissioned pilot | **متحقق** | 7 عقد محلية، WAL، security controls، protocol tests |
| Advanced permissioned reference network | **متحقق** | economics، randomness، availability، execution binding، fuzz، model checks، churn |
| Local long-run rehearsal | **متحقق v5** | 120/120، liveness=1.0، errors=0، event log verified |
| Public testnet حقيقية | **غير متحقق** | يلزم WAN متعددة المضيفين، validators مستقلون، مفاتيح مستقلة، admission مفتوح مضبوط، telemetry وسجل عام لفترة محددة |
| Production mainnet | **غير متحقق وبعيد** | يلزم public testnet ناجحة، تدقيق مستقل، assurance أوسع، economics حقيقية، upgrades وbackup/restore ومقارنات عادلة |

## 5. لماذا لم تُرفع الشبكة إلى Public Testnet؟

العائق الحاسم ليس نقصًا في عدد الاختبارات المحلية، بل غياب البيئة الخارجية التي تجعل النتائج قابلة للتحقق من أطراف مستقلة. جميع النتائج الحالية موسومة `LOCAL_EMULATION`؛ إذ شُغلت العمليات على مضيف واحد وبعناوين loopback. لا يوجد في artifacts الحالية إثبات أن validators يملكون مفاتيح مستقلة على hosts مستقلة أو أن traffic اجتاز WAN حقيقية بمشغلين لا يتحكم بهم مشغل واحد.

اقتصاديًا، ledger المحلي قابل للاستعادة لكنه لا يثبت token custody أو إيداعًا وسحبًا حقيقيين أو reward emission وwithdrawal delay وslashing قابلًا للإنفاذ خارج العملية. كما لا يثبت وحده مقاومة Sybil أو احتكار stake أو تواطؤ المشغلين.

عشوائيًا، commit-reveal وcommitment fallback يحسنان liveness، لكن public testnet تحتاج windows مرتبطة بالحقب، تعريفًا علنيًا للـtimeout، قابلية تدقيق لتدوير اللجنة، وتحليلًا لمصالح المشاركين تحت non-reveal والتواطؤ.

في availability، أصبحت coding وsampling وrepair عملية محليًا، لكن يلزم إثبات provider assignment وretention وpruning وauthenticated sampling وdata withholding على مضيفين منفصلين، مع ربط evidence بالstake وقياس repair تحت فقدان providers فعليين.

في execution، kernel deterministic مفيد ومحدد، لكنه ليس VM عقود عامة. لا توجد بعد لغة عامة آمنة، sandbox formal لبرامج غير موثوقة، storage rent شامل، capability system مكتمل، أو composability عامة تكافئ ما تقدمه منصات عقود ذكية واسعة.

وأخيرًا، لا يجوز تفسير demo HotStuff أو تعذر build Narwhal/Tusk على أنه تفوق أو قصور مطلق. المقارنة العلمية تحتاج workload وhardware وnetwork model وstorage وclient semantics موحدة؛ لذلك يبقى الادعاء الصحيح workload-by-workload، لا «أفضل من جميع البلوكشينات».[1] [2] [3] [4]

## 6. شروط الانتقال التنفيذية إلى WAN Public Testnet

يجب أولًا إنشاء genesis manifest علني يضم network ID وsoftware version وprotocol/wire version وvalidator public keys وstake bonds وregions وavailability roles. لكل validator يجب أن يكون private key مولدًا على مضيفه ولا يغادره، مع CA خاصة بالشبكة وشهادة mTLS، وسجل config digest قابل للتدقيق.

بعد ذلك يجب اجتياز connectivity gate من كل زوج validators: mTLS handshake، frame exchange، timeout، rate limit، replay rejection، malformed frame handling، وقياس latency وpacket loss. ثم تُنفذ مراحل onboarding وstake settlement وbeacon وavailability منفصلة قبل بدء الحمل الطويل.

| البوابة الخارجية | دليل القبول المطلوب | الحالة الحالية |
|---|---|---|
| Identity | مفاتيح عامة فريدة، private keys خارج Git/inventory، operator attestations | **مفقود** |
| Independent hosts | مضيفون ومواضع شبكية ومشغلون مستقلون، مع proof قابل للتدقيق | **مفقود** |
| WAN connectivity | pairwise mTLS/frame tests مع latency/loss/NAT/firewall evidence | **مفقود** |
| Persistent storage | WAL/snapshot/restore بعد power-loss simulation على disk دائم | **جزئي محليًا** |
| Membership/economics | bond/withdraw/slash حقيقي ومعلن وقابل للتدقيق | **جزئي محليًا** |
| Beacon | rounds عبر hosts مستقلة وnon-reveal/fallback evidence | **جزئي محليًا** |
| Availability | providers مستقلة، withholding، repair، sampling evidence | **جزئي محليًا** |
| Observability | metrics، incident IDs، public event log، digest خارجي | **جزئي محليًا** |
| Upgrade safety | compatibility window، migration digest، rollback، operator acknowledgements | **غير مختبر خارجيًا** |
| Long-run | تشغيل لا يقل عن فترة معلنة مع churn وincidents وrestarts | **متحقق محليًا فقط** |

## 7. سياسة الحوادث والترقيات

لا تُنفذ ترقية consensus أو wire schema بصمت. كل ترقية يجب أن تحمل `upgrade_id` ونسخة البرنامج القديمة والجديدة وconfig digest وmigration digest ووقت البدء والنتيجة وقرار rollback. يجب تسجيل crash وrestart وslashing وnon-reveal وrepair وcommittee rotation وupgrade في JSONL append-only، مع نشر digest دوري خارج المضيف.

سجل v5 يثبت وجود hash chain وconfig-upgrade candidate، لكنه لا يثبت ترقية consensus فعلية على شبكة عامة. لذلك بقيت الترقية في حالة `not_applied_to_consensus`، وهو القرار الصحيح في هذه المرحلة لأن تطبيق ترقية غير متوافق قبل وجود governance window قد يضر بسلامة الشبكة.

## 8. الحكم العلمي والهندسي

النتيجة الحالية **تقدم هندسي حقيقي**: أُغلقت فجوات كبيرة في settlement وrandomness incentives وavailability وexecution binding وrestart handling، وأثبت long-run v5 liveness كاملة في سيناريو محلي مع Byzantine وkill/restart وDoS جزئي، مع errors تشغيلية تساوي صفرًا وسجل أحداث قابل للتحقق.

لكن لا توجد بعد أدلة كافية لتسمية MOSAIC public permissionless testnet أو production mainnet، ولا لتأكيد تفوقه على كل أنظمة البلوكشين. التصنيف المنضبط الآن هو: **Advanced Permissioned Reference Network، جاهز للانتقال إلى WAN deployment rehearsal، وليس جاهزًا للإطلاق العام**.

الخطوة التالية الصحيحة هي تعبئة inventory حقيقية، إنشاء مفاتيح وشهادات على hosts مستقلة، تشغيل connectivity ثم gates الأربع منفصلة، وبعدها تشغيل فترة WAN طويلة ونشر event log وmetrics والـincidents. إذا فشلت أي بوابة، يبقى التصنيف كما هو وتُسجل الفجوة بدل رفع التصنيف تسويقيًا.

## المراجع

[1]: https://github.com/hot-stuff/libhotstuff — المستودع الرسمي لـlibhotstuff وdemo binary المستخدم في المقارنة.  
[2]: https://github.com/MystenLabs/narwhal — المستودع الرسمي لـNarwhal/Tusk الذي تعذر بناء binary الكامل له في البيئة الحالية.  
[3]: https://arxiv.org/abs/1803.05069 — ورقة HotStuff الأصلية.  
[4]: https://arxiv.org/abs/2105.11827 — ورقة Narwhal and Tusk.
