# MOSAIC — النموذج النظري والآلية الأساسية

## 1. الكائنات الرياضية

نعرّف `Seal` للمورد `x` في epoch `e` كالتالي:

```text
Seal(x, e, v, r, k) = (resource=x, epoch=e, version=v,
                       state_root=r, capability_hash=k)
```

يمثل `capability_hash` سرًا أو مفتاحًا أحادي الاستعمال مرتبطًا بالختم. لا يجوز انتقال صالح أن يستهلك الختم نفسه مرتين. لا توجد دلالة لـblock height أو global sequence.

الانتقال هو:

```text
Capsule C = (predecessor=P, successor=S, rule=R,
             bundle_id=B, attempt=a, client_sig=σc)
```

حيث `P` ختم سابق، و`S` الحالة المقترحة، و`R` قاعدة انتقال deterministic، و`B` يساوي `⊥` للعملية المحلية أو digest حزمة متعددة المجالات.

نحسب:

```text
D = H("MOSAIC/CAPSULE/v1" || P || S || R || B || a)
```

ولا تُقبل أي شهادة إلا إذا طابقت `D` كاملًا. التوقيع على `D` لا يثبت وحده أن الانتقال نهائي؛ إنه يثبت هوية المنشئ فقط.

## 2. مجموعة الشهود

من دون قائد دائم، تُشتق لجنة الشهود من الختم السابق:

```text
seed = H("MOSAIC/WITNESS-SEED/v1" || P || epoch)
W = CommitteeSelect(seed, membership_snapshot)
```

يجب أن تكون `CommitteeSelect` قابلة لإعادة الإنتاج، وأن تتعامل مع stake، وأن تضمن حدًا أعلى لاحتمال أن تملك Byzantine committee أكثر من ثلث الوزن. هذا الجزء ليس hash بسيطًا في النظام الإنتاجي؛ يحتاج VRF أو randomness beacon وproof of selection.

## 3. Receipt وFirst-Claim Lock

عند استلام كبسولة، يتحقق الشاهد من التوقيع، predecessor، capability، rule، وmembership. إذا لم يسبق له تثبيت claim لهذا predecessor، يسجل:

```text
Receipt = (witness_id, P, D, attempt, epoch,
           status=ACCEPT, σw)
```

ويضع قفلًا محليًا:

```text
lock[P] = (D, attempt, epoch)
```

إذا وصل `D2 ≠ D` لنفس `P` قبل وجود abandonment proof، لا يغير الشاهد القفل؛ بل يولد:

```text
ConflictEvidence = (P, D1, σclient1, D2, σclient2)
```

إذا كانت الكبسولتان موقعتين من العميل نفسه، فهذا دليل equivocation مباشر. وإذا كانتا صادرتين من جهتين مختلفتين على capability نفسها، فهذا يكشف خرقًا في مصدر القدرة أو عضوية النظام ويُعامل كحادث سلامة.

## 4. Closure Proof

تُغلق الكبسولة `D` عندما تجمع receipts متوافقة من نفس `W` بوزن يتجاوز ثلثي وزن اللجنة:

```text
Closure(D) = (P, D, attempt, epoch, receipt_set, σaggregate)
```

في النسخة الأولى يكون `σaggregate` مجموعة توقيعات؛ في النسخة الكاملة يستخدم BLS/threshold signature مع proof يثبت مجموعة الموقعين. لا تقبل العقدة الإغلاق إذا اختلف predecessor أو attempt أو bundle digest بين receipts.

المعنى الدقيق للإغلاق هو:

> يوجد وزن كافٍ من الشهود الصالحين الذين ثبتوا هذا successor، ولا يمكن أن يوجد إغلاق صالح آخر من predecessor نفسه تحت افتراض أن Byzantine weight أقل من الثلث.

لا يوجد تصويت على أي فرع آخر ولا ترتيب بين كبسولات لا تتشارك predecessor.

## 5. لماذا يمنع ذلك إغلاق فرعين

افترض وجود `Closure(D1)` و`Closure(D2)` لنفس `P`، حيث `D1 ≠ D2`. كل إغلاق يملك وزنًا أكبر من `2/3` من اللجنة نفسها، لذلك يتقاطع مجموع الموقعين في وزن أكبر من `1/3`. وبما أن Byzantine weight أقل من `1/3`، يوجد شاهد صادق في التقاطع. قفل `First-Claim` يمنع الشاهد الصادق من إصدار receipt لـ`D1` و`D2`. هذا تناقض؛ إذن لا يمكن وجود الإغلاقين معًا.

هذه الحجة لا تثبت liveness. liveness تحتاج أن الكبسولة الصحيحة تصل إلى وزن كافٍ، وأن القفل العالق يمكن تحريره فقط عبر `AbandonProof` آمن.

## 6. AbandonProof والاسترداد

القفل لا ينتهي بساعة محلية، لأن الساعات لا تثبت شيئًا. إذا فشل العميل في إكمال الكبسولة، يمكن للجنة إصدار:

```text
AbandonProof = (P, D, attempt, reason=TIMEOUT,
                receipts_for_abandon, σaggregate)
```

لا يجوز إصدار `AbandonProof` إذا كان الشاهد يملك `Closure(D)`. بعد اكتمال abandonment، يصبح `P` قابلًا لمحاولة جديدة `attempt+1`. لا يمكن أن يتعايش `Closure(D)` و`AbandonProof(D)` إذا كانت عتبة كل منهما أكبر من الثلثين، لأنهما يتقاطعان في شاهد صادق، والشاهد لا يصوت ضد إغلاق يعرفه.

هذا الاسترداد هو موضع خطر رئيسي: إذا سمحنا بإنشاء attempt جديدة بلا دليل abandonment، يمكن أن نعيد double-spend تحت اسم جديد. لذلك يظل `attempt` جزءًا من كل digest وشهادة.

## 7. تطبيق الحالة

العقدة لا تطبق successor لمجرد receipt أو client signature. الدالة الوحيدة التي تنقل الحالة هي:

```text
apply(P, D, Closure(D))
```

وتتحقق من أن `P` هو الختم الحالي، وأن `Closure(D)` صحيح، وأن `D` يطابق successor وقاعدة الانتقال، ثم تستبدل capability القديمة بالجديدة. إذا وصلت closure بعد تطبيق successor نفسه، تكون العملية idempotent؛ وإذا وصلت closure مختلفة، تُرفض وتُحفظ كـevidence.

## 8. MOSAIC Bundle

للمعاملة التي تمس موارد `P1...Pn` في مجالات مختلفة، ينشئ العميل:

```text
Bundle B = H("MOSAIC/BUNDLE/v1" || D1 || ... || Dn || policy)
```

كل domain يتحقق من capsule المحلية لكنه لا يجعل output قابلاً للصرف. تصدر domains `BundleReceipt` على نفس `B`. يصبح bundle مغلقًا عندما توجد closure صحيحة لكل predecessor required في `B`، وتُنشئ العقدة `BundleClosure(B)` من المتجه الكامل.

قبل `BundleClosure(B)`, المخرجات تكون `PendingCapability` غير قابلة لإعادة الإنفاق. بعد الإغلاق، تتحول كل pending capabilities معًا إلى spendable seals. إذا فشل domain واحد، يمكن إصدار `BundleAbandonProof` يعيد كل pending capabilities إلى حالة recovery محددة مسبقًا؛ لا يوجد rollback لحالة spendable لأن الحالة لم تدخلها أصلًا.

هذا يوفر atomic visibility، لكنه ليس مجانيًا: يحتاج حفظ pending state، expiry/recovery، وإثبات أن `BundleAbandonProof` لا يتعايش مع `BundleClosure`.

## 9. نموذج العضوية

كل witness يملك وزنًا `q_i` في snapshot. العتبة:

```text
Q = floor(2 * sum(q_i) / 3) + 1
```

العضوية ليست مجرد مفتاح. يجب أن تحمل `AdmissionProof` تثبت stake/الحصة، epoch، committee seed، وقيود Sybil. كل تغيير في snapshot يحتاج `MembershipClosure`؛ لا يجوز استخدام لجنة جديدة للتحقق من صلاحية الختم القديم إلا عبر proof انتقال حقبة.

## 10. invariants المستهدفة

| الرمز | invariant |
|---|---|
| M1 | لا يوجد `Closure(D1)` و`Closure(D2)` مختلفان لنفس predecessor |
| M2 | كل receipt وclosure قابل للتحقق تشفيريًا من دون ثقة في المرسل |
| M3 | لا تطبق العقدة successor بلا closure صحيحة |
| M4 | لا تنتج `AbandonProof` مع closure صحيحة للكبسولة نفسها |
| M5 | لا يصبح bundle spendable جزئيًا |
| M6 | لا تزيد هوية إضافية الوزن خارج membership proof |
| M7 | تغيير epoch لا يعيد صلاحية قفل أو شهادة قديمة |
| M8 | كل evidence يثبت إما equivocation أو membership/capability violation |

## 11. حدود النظرية

الآلية لا تلغي الإجماع من الرياضيات؛ إنها تضيق موضوع الاتفاق من ترتيب كل الأحداث إلى قبول successor فريد لكل predecessor. إذا كان التطبيق يحتاج ترتيبًا عالميًا أو smart contract يقرأ حالة غير محلية متغيرة، فسيحتاج إلى طبقة ترتيب أو domain موحد، وعندها لا يجوز تسويق MOSAIC كحل بلا إجماع.

الجدة المحتملة، إن بقيت بعد فحص السوابق، ستكون في **جبر الإغلاق والـabandonment evidence** وطريقة تركيب ذلك مع capabilities وatomic pending visibility. أما التوقيعات، النصاب، UTXO، object-local execution، وcross-shard atomicity فهي مكونات معروفة.
