# MOSAIC Binary Comparison

أُجريت المقارنة على binaries حقيقية قدر الإمكان، مع فصل القياس المباشر عن أرقام الأوراق أو abstractions.

## HotStuff

تم جلب `libhotstuff` الرسمي من مستودعه، وبُنيت المكتبة والأمثلة محليًا بعد تثبيت تبعيات CMake وLibuv وOpenSSL وautotools. احتاجت dependency `salticidae` إلى include قياسي مفقود (`<cstdint>`) للتوافق مع toolchain الحالية؛ لم يتغير كود consensus أو message protocol.

شُغّل demo الرسمي بأربع replicas وclient حقيقي. سجّل client **10,710 قرارات نهائية** بين أول وآخر timestamp في حوالي **9.988412 s**، أي throughput مرصود تقريبي **1,072.242 قرارًا/ثانية** في هذا demo. ظهرت أسطر `got <fin decision=1` لكل قرار، لكن هذا القياس لا يستخدم WAL أو نموذج موارد MOSAIC أو نفس حجم المعاملة، لذلك لا يجوز اعتباره تفوقًا أو هزيمة مباشرة.

## Narwhal/Tusk

جُلب مستودع Narwhal الرسمي وحاولت عملية `cargo build --release --workspace`، ثم محاولة بناء الحزم الأساسية. توقف البناء في `librocksdb-sys v0.8.0+7.4.4` بسبب panic في bindgen/proc-macro2 القديم عند توليد identifier من RocksDB headers. لذلك لا توجد نتيجة binary TPS/latency صالحة لـNarwhal في هذه البيئة، ولا يجوز استبدالها بأرقام README المنشورة.

## MOSAIC

MOSAIC شُغّل كـ7 عمليات TCP مستقلة مع WAL والأمان والـretries، وفي السيناريو المركب الأخير مع عقدتين Byzantine، kill/restart، وpartial-frame DoS نجحت **30/30**، وكان p50 **35.171657 ms** وp95 **47.187885 ms**. هذه نتيجة MOSAIC قابلة لإعادة التشغيل في localhost process test، لكنها ليست نفس workload HotStuff demo، ولذلك تُحفظ كـbaseline داخلية لا كترتيب عالمي.

| النظام | المصدر | التنفيذ الفعلي | القياس المرصود | قابلية المقارنة الحالية |
|---|---|---:|---:|---|
| MOSAIC | `/home/ubuntu/blockchain_alt` | نعم، 7 TCP processes + WAL + Byzantine + DoS | 30/30، p95 47.19 ms | baseline داخلية؛ semantics مختلفة |
| HotStuff | `libhotstuff` الرسمي | نعم، 4 replicas + official demo client | 10,710 final decisions، نحو 1,072/s | binary evidence؛ workload مختلف |
| Narwhal/Tusk | المستودع الرسمي | لا، build توقف عند librocksdb-sys | لا يوجد رقم صالح | غير قابل للقياس في هذه البيئة |

> لا يدعم هذا التقرير ادعاء أن MOSAIC أسرع من HotStuff أو Narwhal/Tusk. المقارنة العلمية النهائية تتطلب نفس hardware، نفس عدد العقد، نفس transaction size، WAL/security parity، نفس failure model، ونفس definition of finality.
