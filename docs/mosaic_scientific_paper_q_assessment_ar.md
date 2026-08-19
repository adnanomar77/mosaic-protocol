# تقييم MOSAIC كبحث علمي وتصنيف المجلات المستهدف

**التاريخ:** 2026-08-19  
**الحكم المختصر:** MOSAIC صالح كأساس لبحث علمي في distributed systems وdistributed ledger technology، لكنه في حالته الحالية أقرب إلى prototype paper أو systems-design paper مدعوم بتقييم محلي، وليس بعد بحثًا قويًا جاهزًا بثقة لمجلة Q1.

## 1. تصحيح مفهوم Q

> **Q1 وQ2 وQ3 وQ4 تصنيفات للمجلة، لا للبحث نفسه.**

يتغير التصنيف بحسب قاعدة البيانات، والسنة، والفئة الموضوعية. فقد تكون المجلة Q1 في Computer Networks وQ2 في Information Systems أو العكس. كما أن Q لا يعني أن كل ورقة في المجلة لها الجودة نفسها، ولا يعني أن إرسال الورقة إلى مجلة Q1 سيجعلها بحثًا Q1.

## 2. هل يصلح MOSAIC كبحث علمي؟

نعم، بشرط تحويل المستودع الحالي إلى مساهمة علمية محددة لا إلى وصف شامل لكل المكونات. الشكل الأنسب هو بحث systems/protocol research يطرح سؤالًا قابلًا للاختبار:

> هل يمكن لنموذج state-transition-centric قائم على Capsule وStateSeal وClosureProof وobligation evidence أن يوفر سلامة قابلة للتحقق وتنفيذًا موازيًا وتكلفة اتصال مقبولة، مقارنةً ببروتوكولات block/log أو object-centric القريبة، من دون فقدان liveness تحت التعارض وإعادة التشغيل؟

يمتلك المشروع مادة أولية قوية لهذا النوع من الورقة: protocol core، implementation، WAL/recovery، security controls، execution binding، availability، incentives، bounded model checking، fuzzing، وlong-run local rehearsal. لكن الورقة الحالية لا ينبغي أن تدعي أن MOSAIC بديل مثبت لكل blockchain أو أنه أسرع وأكثر أمنًا من الجميع.

## 3. التقييم الحالي لنضج الورقة

| المحور | التقييم الحالي | أثره على النشر |
|---|---|---|
| فكرة ومشكلة بحثية | قوية وقابلة لصياغة مساهمة | تحتاج تضييقًا إلى claim واحد أو اثنين |
| prototype | جيد ومتعدد الطبقات | نقطة قوة إذا أُرفق artifact قابل لإعادة الإنتاج |
| correctness | bounded checks وTLA+ أولية | غير كافٍ كـformal proof؛ بعض invariants الحالية ضعيفة أو معرفة كـTRUE |
| experimental evidence | 87/87 tests و120/120 محليًا وliveness=1.0 | قوي كـprototype evidence، لكنه ليس WAN أو public testnet |
| novelty | تركيب معماري محتمل | يحتاج related-work وnovelty matrix ضد Sui-style وNarwhal/Tusk وHotStuff وFastPay وغيرها |
| baseline comparison | HotStuff demo شُغّل، Narwhal build تعثر | غير كافٍ لمقارنة أداء عادلة؛ يجب توحيد workload وhardware وnetwork model |
| threat model | موجود جزئيًا | يحتاج تعريفًا رسميًا للـByzantine، Sybil، stake concentration، data withholding، key compromise |
| reproducibility | كود واختبارات وartifacts موجودة | يحتاج repository release وscripts وconfig وdata/code availability statement |
| public deployment | غير متحقق | يمنع الادعاء بأنه permissionless public network |

## 4. مستوى النشر الواقعي

التقدير التالي هو **نطاق جاهزية للمخطوط** وليس تصنيفًا مضمونًا للورقة:

| حالة النسخة | النطاق الواقعي | الحكم |
|---|---|---|
| النسخة الحالية كما هي، مع local emulation فقط | ورقة prototype أو systems-design؛ غالبًا Q3/Q4 أو workshop/conference مناسب | قابلة للتقديم، لكنها معرضة لملاحظات جوهرية حول novelty وWAN وformal guarantees |
| بعد تضييق claim، related-work عميق، specification أقوى، artifacts، ومقارنة موحدة محلية/محاكية | **Q2 هدف واقعي** في venue متخصص في DLT أو distributed systems التطبيقية | ممكنة إذا كانت النتائج قابلة لإعادة الإنتاج والادعاءات منضبطة |
| بعد WAN مستقلة طويلة، formal safety/liveness أقوى، novelty واضحة، baselines عادلة، وartifact evaluation | **Q1 هدف ممكن لكنه تنافسي** | لا يوجد ضمان قبول؛ يحتاج مساهمة عامة تتجاوز prototype هندسيًا |
| Q1 عالي الانتقائية في security/dependability أو distributed computing | **هدف طموح** | يتطلب theorem أو guarantees قوية، threat model كاملًا، تقييمًا كبيرًا، ومقارنة state-of-the-art مقنعة |

## 5. مجلات مناسبة بحسب زاوية الورقة

| المجلة | التصنيف الظاهر في المصدر | الملاءمة لـMOSAIC | صعوبة التقديم الحالية |
|---|---|---|---|
| Blockchain: Research and Applications | SJR 2025: Q1 في Computer Networks and Communications وComputer Science Applications وInformation Systems | الأنسب إذا كان التركيز على blockchain/DLT architecture وevaluation وnovel techniques | عالية؛ النسخة الحالية تحتاج WAN وnovelty evidence أقوى |
| Distributed Ledger Technologies: Research and Practice | SJR 2025: Q2 في Information Systems وManagement Information Systems، وQ3 في Computer Science Applications | تطابق موضوعي مباشر مع DLT والتطوير والنشر والتقييم | هدف واقعي بعد إعادة صياغة الورقة، لكن لا يزال يحتاج contribution واضحًا |
| Journal of Parallel and Distributed Computing | SJR 2025: Q1 في Computer Networks and Communications وTheoretical Computer Science | مناسب إذا تحولت الورقة إلى protocol theory وdistributed execution مع evaluation عميق | عالية جدًا؛ prototype وحده لا يكفي |
| Computer Networks | SJR 2025: Q1 في Computer Networks and Communications | مناسب إذا كان جوهر الورقة protocol/networking performance وWAN evaluation | عالية؛ يلزم قياس شبكي عادل ونتائج واسعة |
| IEEE Transactions on Dependable and Secure Computing | SJR 2025: Q1 في الفئات الظاهرة | مناسب فقط إذا كان الإسهام الأساسي dependability/security مع formal threat model وضمانات | عالية جدًا؛ الأدلة الحالية غير كافية بعد |
| Future Generation Computer Systems | نطاقه يشمل distributed systems وprotocols وverification وsecurity | مناسب لنسخة systems واسعة إذا أضيفت scale وwide-area evaluation | يتطلب تقييمًا أوسع من local multi-process |

توضح مصادر SCImago أن `Blockchain: Research and Applications` مصنفة Q1 في الفئات الثلاث الظاهرة لعام 2025، وأن `Distributed Ledger Technologies: Research and Practice` مصنفة Q2 في Information Systems وManagement Information Systems وQ3 في Computer Science Applications لعام 2025. كما أن `Journal of Parallel and Distributed Computing` و`Computer Networks` و`IEEE Transactions on Dependable and Secure Computing` تظهر Q1 في فئات ذات صلة لعام 2025.[1] [2] [3] [4] [5]

## 6. ما الذي يجب إنجازه قبل استهداف Q1؟

أولًا، يجب تثبيت claim علمي واحد. لا ينبغي أن تقول الورقة إن MOSAIC أسرع وأمن وأخف وأفضل من كل الأنظمة. الصياغة الأقوى هي ادعاء محدد قابل للقياس، مثل أن obligation capsules وclosure proofs تقلل كلفة التنسيق في workload معين أو تقدم evidence أقوى للتعارض مع الحفاظ على liveness ضمن نموذج محدد.

ثانيًا، يجب تحويل TLA+ من bounded sketch إلى specification أكثر صرامة. المواصفة الحالية تصرح بتجريد التوقيعات إلى `HonestNonEquivocation`، وبعض invariants مثل M5 وM8 معرفة `TRUE`، وM7 لا تقيس إلا شرطًا ضعيفًا. لذلك يجب تعريف transition relation وquorum weights وepochs وavailability وexecution semantics بصورة غير تافهة، ثم تقديم invariant proofs أو model checking يختبرها فعلًا.

ثالثًا، يجب تنفيذ comparison matrix عادلة ضد HotStuff وNarwhal/Tusk وSui-style object-centric workload وFastPay-style certificates، مع hardware وnetwork delay وmessage loss وpayload وclient load وfailure schedule موحدة. لا يكفي تشغيل demo مختلف ثم مقارنة رقم throughput.

رابعًا، يجب تنفيذ WAN testnet بمشغلين مستقلين، وقياس latency distribution وthroughput وbytes/operation وstorage growth وrecovery وavailability repair وcommittee rotation، مع event log عام وincidents وupgrade windows. حينها تصبح نتيجة `LOCAL_EMULATION` دليلًا تمهيديًا لا الدليل الرئيسي.

خامسًا، يجب إضافة threat model وeconomic analysis وnovelty review عميق. يجب تحديد ما الذي لا يستطيع Byzantine adversary فعله، وما الذي يحدث تحت Sybil أو stake concentration أو collusion أو data withholding أو key compromise، وما الفرضيات الاقتصادية التي تجعل bond/slash/reward فعالة.

## 7. الحكم النهائي

**ينفع MOSAIC كبحث علمي، وبدرجة جيدة كبحث prototype/protocol design.** لا أعتبر النسخة الحالية جاهزة بصدق لادعاء Q1، ولا أستطيع إعطاء البحث نفسه تصنيف Q؛ فالـQ للمجلة.

التقدير العملي هو أن النسخة الحالية يمكن أن تبدأ كورقة workshop أو venue متخصص، وقد تكون في نطاق **Q3/Q4 من حيث نضج الأدلة إذا أُرسلت الآن**. بعد إكمال WAN، formalization، novelty matrix، baselines العادلة، وartifact reproducibility، يصبح **Q2 هدفًا واقعيًا**. أما **Q1 فهو هدف ممكن لكنه غير مضمون وتنافسي**، ويتطلب أن تثبت الورقة مساهمة بروتوكولية عامة لا مجرد نظام يعمل محليًا.

أفضل استراتيجية ليست إرسال النسخة الحالية مباشرة إلى مجلة Q1، بل بناء ورقة أولى بعنوان يركز على المساهمة القابلة للإثبات، ثم إغلاق الفجوات التجريبية والنظرية، وبعدها استهداف `Blockchain: Research and Applications` أو `Computer Networks` أو `Journal of Parallel and Distributed Computing` بحسب الزاوية النهائية. وإذا بقي التركيز على DLT deployment/evaluation، فإن `Distributed Ledger Technologies: Research and Practice` هو هدف أكثر واقعية من حيث topical fit.

## المراجع

[1]: https://www.scimagojr.com/journalsearch.php?q=21101101317&tip=sid&clean=0 — SCImago: Blockchain: Research and Applications، بيانات SJR 2025 ونطاق المجلة.  
[2]: https://www.scimagojr.com/journalsearch.php?q=21101306831&tip=sid&clean=0 — SCImago: Distributed Ledger Technologies، بيانات SJR 2025 ونطاق المجلة.  
[3]: https://www.scimagojr.com/journalsearch.php?q=25621&tip=sid — SCImago: Journal of Parallel and Distributed Computing، بيانات SJR 2025 ونطاق المجلة.  
[4]: https://www.scimagojr.com/journalsearch.php?q=26811&tip=sid — SCImago: Computer Networks، بيانات SJR 2025 ونطاق المجلة.  
[5]: https://www.scimagojr.com/journalsearch.php?q=28918&tip=sid&clean=0 — SCImago: IEEE Transactions on Dependable and Secure Computing، بيانات SJR 2025 ونطاق المجلة.  
[6]: https://www.sciencedirect.com/journal/future-generation-computer-systems — صفحة Future Generation Computer Systems، scope وخيارات النشر.  
[7]: https://www.acm.org/media-center/2022/october/dlt-inaugural-issue — إعلان ACM عن نطاق Distributed Ledger Technologies: Research and Practice.
