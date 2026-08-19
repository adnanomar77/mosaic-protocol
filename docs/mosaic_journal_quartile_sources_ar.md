# مصادر تقييم مجلات MOSAIC وتصنيفها

**تاريخ التحقق:** 2026-08-19.  
**ملاحظة منهجية:** Q تصنيف للمجلة بحسب الفهرس والفئة والسنة، وليس تصنيفًا للبحث نفسه ولا ضمانًا لقبوله.

| المجلة | نطاق ملائم لـMOSAIC | أحدث نتيجة SJR ظاهرة في المصدر | الفئة/السنة | المصدر |
|---|---|---:|---|---|
| Blockchain: Research and Applications | blockchain theory, applications, advanced methodologies، والاتجاهات غير المحلولة | SJR 2025 = 1.302، Q1 | Computer Networks and Communications، Computer Science Applications، Information Systems؛ 2025 | https://www.scimagojr.com/journalsearch.php?q=21101101317&tip=sid&clean=0 |
| Distributed Ledger Technologies: Research and Practice | research/development، deployment، evaluation of DLT وblockchain وsmart contracts | SJR 2025 = 0.456، Q2 في Information Systems وManagement Information Systems، Q3 في Computer Science Applications | 2025 | https://www.scimagojr.com/journalsearch.php?q=21101306831&tip=sid&clean=0 |
| Journal of Parallel and Distributed Computing | theory, design, evaluation and use of distributed systems | SJR 2025 = 0.876، Q1 في Computer Networks and Communications وTheoretical Computer Science | 2025 | https://www.scimagojr.com/journalsearch.php?q=25621&tip=sid |
| IEEE Transactions on Dependable and Secure Computing | foundations, modeling, design, evaluation، security/dependability/performance | SJR 2025 = 1.758، Q1 | Computer Science (miscellaneous) وElectrical and Electronic Engineering؛ 2025 | https://www.scimagojr.com/journalsearch.php?q=28918&tip=sid&clean=0 |
| Computer Networks | archival research in computer communications and networking، protocols and implementations | SJR 2025 = 1.144، Q1 | Computer Networks and Communications؛ 2025 | https://www.scimagojr.com/journalsearch.php?q=26811&tip=sid |
| Future Generation Computer Systems | distributed systems، protocols، verification، security، wide-area systems | صفحة المجلة تعرض نطاق distributed systems/protocols/verification وCiteScore/Impact Factor؛ لم يُستخدم ذلك وحده لتحديد Q | scope verified from publisher page | https://www.sciencedirect.com/journal/future-generation-computer-systems |
| ACM DLT journal announcement | peer-reviewed venue للبحث والتطوير والنشر والتقييم في DLT | لا يُستنتج Q من الإعلان؛ استُخدم لتثبيت scope | source announcement | https://www.acm.org/media-center/2022/october/dlt-inaugural-issue |

## استنتاجات

المسار الأنسب للمقالة يعتمد على صياغتها النهائية. إذا كان التركيز على protocol novelty وdistributed-systems theory فالمجلات ذات نطاق JPDC أو Computer Networks/FGCS أقرب. إذا كان التركيز على الأمن والـdependability والـformal guarantees فـTDSC هو الهدف الأعلى صعوبة. إذا كان التركيز على DLT implementation/evaluation فـBlockchain: Research and Applications أو ACM DLT أكثر تطابقًا من حيث الموضوع.

لا يعني كون المجلة Q1 أن الورقة Q1 تلقائيًا. الورقة تحتاج novelty قابلة للدفاع، تعريفًا formal، guarantees محددة، مقارنة عادلة، reproducibility، ونتائج WAN أو testbed مستقلة. كما أن SCImago وJCR قد يقدمان تصنيفات مختلفة حسب الفئة والسنة؛ يجب تحديد الفهرس الذي تتطلبه الجهة الأكاديمية قبل اختيار الهدف.

## ملاحظات على MOSAIC مقابل متطلبات الورقة

النسخة الحالية تملك prototype واختبارات محلية وlong-run محليًا، لكنها لا تملك بعد WAN مستقلة أو novelty audit مكتمل أو formal proof غير محدود. مواصفة TLA+ الحالية تصف bounded safety model، وتصرح بنفسها بأن التشفير مختزل إلى HonestNonEquivocation؛ كما أن بعض invariants مثل M5 وM8 معرفة `TRUE`، وM7 ضعيفة جدًا. لذلك يجب عدم تقديمها كإثبات نظري كامل.
