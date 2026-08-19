# مصادر baselines الرسمية للمقارنة

## HotStuff / libhotstuff

المستودع الرسمي `hot-stuff/libhotstuff` يصف نفسه بأنه مكتبة BFT عامة، ويذكر أن المستودع يتضمن prototype implementation المقيمة في ورقة HotStuff. كما يذكر أن اختبار fault-tolerance يتضمن إيقاف replica وعودة leader rotation، وأن persistent protocol state كان ضمن TODO في المستودع وقت الاطلاع. المصدر: https://github.com/hot-stuff/libhotstuff

## Narwhal/Tusk

المستودع الرسمي `MystenLabs/narwhal` يذكر أن التطوير اللاحق انتقل إلى Sui، ويحتوي على تنفيذ Rust وbenchmark scripts. المثال المنشور في README يستخدم 4 عقد، وinput rate قدره 50,000 tx/s، ويعرض 46,478 consensus TPS، و464 ms consensus latency، و46,149 end-to-end TPS، و557 ms end-to-end latency. هذه أرقام إعداد Narwhal المنشور، وليست نتيجة MOSAIC ولا ينبغي مقارنتها مباشرة بقياس localhost مختلف. المصدر: https://github.com/MystenLabs/narwhal

## Sui Consensus / Mysticeti

توثيق Sui يذكر أن validator set والـstake يتغيران عند epoch boundaries، وأن quorum يتطلب أكثر من ثلثي الوزن، كما يذكر نتائج controlled testing لـMysticeti: 300,000 TPS على 10 عقد قبل تجاوز latency ثانية، و400,000 TPS على 50 عقد، ومتوسط commitment يقارب 0.5 ثانية مع sustained throughput يقارب 200,000 TPS. الصفحة نفسها تنبه إلى أن هذه controlled benchmark results وليست production metrics. المصدر: https://docs.sui.io/develop/sui-architecture/consensus

## Sui Lutris

ملخص ورقة Sui Lutris يذكر أن النظام يدمج consensusless agreement للمعاملات المستقلة مع consensus للمعاملات المتعارضة، ويذكر latency أقل من 0.5 ثانية عند 5,000 certificates/s، أي 150k ops/s مع transaction blocks. هذه نتيجة ورقة وبإعدادها الخاص، وليست baseline binary يجب إسقاطها مباشرة على MOSAIC. المصدر: https://arxiv.org/abs/2310.18042

## قاعدة المقارنة العادلة

لا تُقارن هذه الأرقام بنتائج MOSAIC الحالية إلا بعد تشغيل binary فعلي أو harness رسمي لكل نظام، على نفس عدد العقد، ونفس نوع المعاملة، وحجم الرسالة، ومقدار الـstake، ونفس شبكة WAN أو emulation، ونفس تعريف finality وthroughput. المقارنة الحالية داخل `run_unified_comparison.py` هي controlled abstraction فقط، وقد صُممت لتقدير تكلفة المعمارية لا لإثبات تفوق إنتاجي.
