# مصفوفة الجدة — MOSAIC

## خلاصة الفحص

لا توجد في هذا الفحص قرينة تسمح بادعاء أن MOSAIC «مبتكر بالكامل». على العكس، العناصر الأساسية موزعة على سوابق قوية. لذلك نُعرّف الجدة المحتملة كتركيب محدد يجب اختباره، لا كادعاء شامل.

| العنصر | سابقة قريبة | الحكم |
|---|---|---|
| تحقق محلي من مدخل أحادي الاستعمال | UTXO/eUTXO | معروف؛ لا يكفي للجدة |
| معاملات مملوكة بلا ترتيب عالمي لكل عملية | FastPay، Sui Lutris | معروف جزئيًا |
| objects كموارد من الدرجة الأولى | Sui Lutris | معروف |
| فصل نشر البيانات عن الإجماع | Narwhal/Tusk | معروف |
| ترتيب يعتمد read/write sets | براءة IBM US12141125B2 | معروف ومغطى برائيًا على مستوى الفكرة العامة |
| معاملات عابرة للشظايا ذرية | TCS وReconfigurable Atomic Commit وThunderbolt | معروف ومثبت نظريًا بأشكال متعددة |
| إعادة تهيئة غير حاجزة | Sui Lutris وThunderbolt | معروف جزئيًا |
| capability lineage + uniqueness closure + conflict evidence | لم يظهر تطابق كامل في الفحص الأولي | مرشح فجوة، غير مثبت |
| جعل الفروع المتعارضة غير قابلة للإغلاق بدل اختيار فائز | يحتاج فحصًا أعمق؛ قد يكون مكافئًا لعدم equivocation/UTXO locking في أعمال سابقة | مرشح فرضية، لا ادعاء |
| bundle قابل للصرف فقط بعد closure دون rollback عالمي | قريب من commit capabilities وatomic commit؛ الفرق يحتاج صياغة رسمية | مرشح فرضية، لا ادعاء |

## نتيجة المرحلة

تُرفض الصياغة الواسعة: «MOSAIC بديل جديد بالكامل للبلوكشين». الصياغة القابلة للدفاع مؤقتًا هي: **نبحث في بروتوكول إغلاق لحالات خطية يجعل فرادة successor قابلة للإثبات محليًا، ويحوّل التعارض إلى evidence يمنع الإغلاق بدل ترتيب الفروع، مع ذرية bundle تعتمد على قابلية الصرف لا rollback**.

لإثبات الجدة العلمية، يجب أن يثبت النموذج أن هذه الآلية ليست مجرد إعادة تسمية لـUTXO أو FastPay أو Sui owned-object path أو TCS، وأنها تضيف invariant أو حد أداء لا تحققه تلك الأعمال. ولإثبات الجدة البرائية، يجب إجراء بحث قانوني احترافي في المطالبات لا الاكتفاء بملخصات محركات البحث.

## المراجع التي تمت قراءتها

1. [FastPay](https://arxiv.org/abs/2003.11506)
2. [Sui Lutris](https://arxiv.org/abs/2310.18042)
3. [Formalizing and Implementing Distributed Ledger Objects](https://arxiv.org/abs/1802.07817)
4. [Cardano EUTXO explainer](https://docs.cardano.org/about-cardano/learn/eutxo-explainer)
5. [Reconfigurable Atomic Transaction Commit](https://arxiv.org/abs/1906.01365)
6. [Thunderbolt](https://arxiv.org/abs/2407.09409)
7. [US12141125B2 Transaction reordering in blockchain](https://patents.google.com/patent/US12141125B2/en)
