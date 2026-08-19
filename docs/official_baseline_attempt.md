# محاولة تشغيل التنفيذات الرسمية المرجعية

## HotStuff

ثُبّت commit المرجعي `dc01ac8626a64342f6a76ae6f8914535dd090bdd` من مستودع `asonnino/hotstuff`. احتاج البناء إلى Rust أحدث لأن dependency حديثة استخدمت `edition2024`، فتم تثبيت Rust 1.97.1 عبر rustup، مع Clang وtmux وFabric واعتماديات Python في بيئة معزولة.

بدأ `cargo build --release` بتنزيل الاعتماديات بنجاح، لكنه بقي أكثر من عشر دقائق في بناء RocksDB/librocksdb-sys ولم ينتج binary ضمن مهلة الاختبار. أُوقفت العملية لتجنب استهلاك الموارد. لا توجد نتيجة HotStuff رسمية من هذه الجلسة.

## Narwhal/Tusk

ثُبّت commit المرجعي `f5145b7219f62b4607be65822d4e3c13147ce778`، وتمت قراءة benchmark الرسمية التي تستخدم Rust وFabric وtestbed محليًا. لم يُشغّل benchmark الرسمي بعد لأن بناء HotStuff المرجعي توقف أولًا عند RocksDB، ولأن المقارنة تحتاج تثبيت إعدادات ووقت ونسخة متطابقة بين التنفيذات.

## النتيجة المنهجية

تم تنفيذ شبكة CCD/NEXUS الحقيقية محليًا عبر TCP وعمليات مستقلة، كما تم تنفيذ مقارنة controlled abstractions في نفس بيئة Python. هذه المقارنة ليست نتائج التنفيذات الرسمية، ولذلك يظل الادعاء الصحيح هو أن CCD/NEXUS اجتاز اختبار شبكة محلية وfault injection أوليًا، بينما المقارنة الرسمية مع binaries الأصلية مؤجلة بسبب تعذر البناء ضمن بيئة الجلسة.

المراجع: [HotStuff repository](https://github.com/asonnino/hotstuff)، [Narwhal/Tusk repository](https://github.com/asonnino/narwhal)، [Sui Lutris paper](https://arxiv.org/abs/2310.18042).
