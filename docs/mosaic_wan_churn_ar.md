# MOSAIC WAN/Churn Test

أضيف `run_mosaic_churn.py` لتشغيل عقد MOSAIC كعمليات TCP مستقلة مع SQLite WAL، ثم قتل عقدة بـSIGKILL أثناء التسلسل، وإعادة تشغيلها من نفس ملف WAL، وإرسال partial frames عدائية، وإعادة محاولة المعاملات transiently الفاشلة.

في السيناريو المركب الأخير شُغلت 7 عقد و30 عملية، مع عقدتين Byzantine (`w0`, `w1`)، وقُتلت `w1` عند العملية 10، ثم أعيد تشغيلها من WAL. نجحت العمليات **30/30**، وكان p50 نحو **35.448113 ms** وp95 نحو **47.187885 ms**، وأُغلقت **24 partial frames** بسبب timeout. بقيت `errors=0` في العقد، بينما ظهرت `transport_failures` منفصلة أثناء churn، وسُجلت تعارضات Byzantine كـ`conflicts` بدل أخطاء تشغيلية.

أضيفت metrics منفصلة لـ`frame_timeouts` و`malformed_frames` و`protocol_rejections` و`transport_failures` و`error_types`، حتى لا تختلط الانقطاعات الطبيعية أو رفض التعارضات مع أخطاء protocol. هذا الاختبار ما زال localhost WAN-emulation وليس إنترنت حقيقيًا؛ الخطوة التالية هي تشغيل نفس السيناريو عبر عدة hosts وشبكة WAN حقيقية أو emulator مع clock skew وNAT وchurn أطول.
