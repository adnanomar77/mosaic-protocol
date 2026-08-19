
# سجل فحص السوابق — MOSAIC

## Sui Lutris

المصدر الأصلي: https://arxiv.org/abs/2310.18042 (v5، 30 Oct 2024). يصف Sui Lutris منصة هجينة تستخدم اتفاقًا بلا إجماع للمعاملات المؤهلة، وتؤخر المعاملات التي قد تتعارض حتى يُحل الترتيب الكلي. كما تستخدم objects كموارد من الدرجة الأولى، وتناقش السلامة أثناء إعادة التهيئة وequivocation. هذه سابقة قريبة جدًا من فكرة MOSAIC في fast path والكائنات؛ لذلك لا يمكن اعتبار «عدم ترتيب كل العمليات» جديدًا وحده.

الفرق المرشح الذي يجب فحصه هو أن MOSAIC لا يملك fast path يقبل العملية ثم يرسل التعارض إلى consensus عالمي؛ بل يحاول أن يجعل الإغلاق نفسه شهادة فرادة successor، وأن يجعل successor المتعارضين غير قابلين للإغلاق مع Conflict Evidence. يجب إثبات أن هذا ليس إعادة صياغة لمسار Sui المملوك أو آليات object-local locking.

## Formalizing and Implementing Distributed Ledger Objects

المصدر الأصلي: https://arxiv.org/abs/1802.07817 (v2، 4 May 2018). يعرّف ledger object كسلسلة من السجلات، ويعرض consistency guarantees مثل atomic/linearizable وsequential وeventual، مع تنفيذات فوق Atomic Broadcast، إضافة إلى validated ledger. هذه سابقة عامة على formalization للحالة والتحقق من السجلات، لكنها لا تطابق آلية MOSAIC المقترحة التي لا تمثل الحقيقة كسلسلة سجلات عالمية.

## نتيجة مؤقتة

الجدة المحتملة ليست في state seals أو signatures أو object-centric execution منفردة؛ هذه العناصر مسبقة. الجدة المرشحة الضيقة هي تركيب «خطية capability + إغلاق فرادة محلي + تعارض كدليل إبطال + bundle قابل للصرف فقط بعد closure» دون ترتيب عالمي أو rollback منسق. يلزم فحص إضافي لـ UTXO/eUTXO، FastPay، Aptos/Sui object consensus، Byzantine atomic broadcast، fraud proofs، وpatents قبل اعتماد هذا الادعاء.

## FastPay

المصدر الأصلي: https://arxiv.org/abs/2003.11506 (v3، 3 Nov 2020). FastPay يستخدم Byzantine Consistent Broadcast بدل full atomic commit channels، ويستهدف pre-funded payments مع latency منخفضة وparallelism عبر authorities. هذه سابقة قوية لفكرة finality بلا ترتيب عالمي لكل المدفوعات؛ لذلك MOSAIC لا يمكنه اعتبار «لا consensus للعمليات المستقلة» ابتكارًا وحده.

الفرق المرشح يبقى أوسع من الدفع: MOSAIC يريد كبسولات انتقال عامة ذات predecessor capability، closure على فرادة successor، وbundle atomic قابل للصرف عبر domains. يجب اختبار ما إذا كانت هذه الإضافة مجرد تعميم معروف لـ FastPay أو Sui.

## Cardano EUTXO

المصدر: https://docs.cardano.org/about-cardano/learn/eutxo-explainer. EUTXO يثبت أن كل output يُستهلك مرة واحدة، وأن التحقق يعتمد على transaction وinputs ويمكن أن يتم محليًا قبل النشر، مع parallelism للمعاملات التي لا تستهلك input نفسه. هذه مطابقة مفاهيمية كبيرة مع linear capability وlocal validation في MOSAIC.

بالتالي لا يجوز تقديم StateSeal أو single-use successor وحدهما كجدة. ما يجب إثباته هو أن MOSAIC يقدم بروتوكول إغلاق Byzantine وشهادة تعارض وbundle closure مختلفًا جوهريًا عن UTXO/eUTXO، لا مجرد UTXO مع اسم جديد.

## براءة Transaction Reordering in Blockchain

المصدر: https://patents.google.com/patent/US12141125B2/en. البراءة تصف endorsement لمجموعة معاملات، read-set/write-set، ثم ordering service يرتب المجموعة اعتمادًا على مجموعات القراءة والكتابة قبل commit. هذا يثبت أن conflict-aware ordering وتقليل invalidated transactions لهما سوابق برائية مباشرة. MOSAIC يختلف فقط إذا أثبت أنه لا يحتاج ordering service ولا يحول التعارض إلى ترتيب، بل إلى evidence يمنع إغلاق الفرعين.

## Reconfigurable Atomic Transaction Commit

المصدر: https://arxiv.org/abs/1906.01365. العمل يعرّف Transaction Certification Service لمعاملات تمتد عبر shards، ويقدم atomic commit مع reconfiguration وبراهين صحة. هذا يجعل ادعاء «bundle closure عبر المجالات» غير كافٍ للجدة. يجب أن يثبت MOSAIC أن قابلية الصرف المؤجلة وConflict Evidence يزيلان تنسيق commit أو يقللان افتراضاته، لا أنهما اسمان جديدان لـTCS/2PC.

## Thunderbolt

المصدر: https://arxiv.org/abs/2407.09409 (v5، 2 Jul 2025). Thunderbolt يقدم شarding فوق DAG، ويفصل single-shard وcross-shard، ويستخدم EOV للمعاملات المحلية وOE للمعاملات العابرة، مع dynamic concurrency controller دون read/write sets مسبقة، وnon-blocking reconfiguration. هذه سابقة حديثة قريبة جدًا من هدف الأداء والذرية في MOSAIC.

نتيجة الجدة: لا يمكن اعتبار «parallel local execution + cross-domain atomicity + non-blocking reconfiguration» جديدًا منفردًا. يجب أن يتجاوز MOSAIC ذلك بآلية مختلفة في معنى الإغلاق نفسه: لا DAG coordination ولا ordering بين أنواع المعاملات، بل capability lineage وشهادة uniqueness/conflict. وحتى هذا الفرق يحتاج فحص النص الكامل والبراءات قبل أي ادعاء.
